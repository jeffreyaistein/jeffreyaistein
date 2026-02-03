"""
Epstein Corpus Ingestor

Ingests documents from local files, sanitizes them, and stores
only safe summaries in the knowledge_documents table.

Safety Constraints:
- All documents pass through ContentSanitizer
- Blocked documents are logged but not stored
- Only sanitized_summary is stored (never raw explicit content)
- Idempotent: re-running does not duplicate documents
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import structlog

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.corpus.sanitizer import ContentSanitizer, SanitizationAction, get_sanitizer
from .readers import (
    read_documents_from_directory,
    read_csv_documents,
    read_json_documents,
    read_jsonl_documents,
    read_text_documents,
    read_parquet_documents,
    FileReadStats,
    get_current_file_stats,
)

logger = structlog.get_logger(__name__)


# Source name constants
SOURCE_KAGGLE = "kaggle_epstein_ranker"
SOURCE_HF = "hf_epstein_index"
SOURCE_DOCS = "epstein_docs"


@dataclass
class FileStats:
    """Statistics for a single file processed."""
    file_path: str
    file_type: str
    records_read: int = 0
    candidates_produced: int = 0
    ingested: int = 0
    blocked: int = 0
    duplicates: int = 0
    errors: int = 0
    # Reader-level skips (from FileReadStats)
    skipped_empty_text: int = 0
    skipped_no_text_field: int = 0
    skipped_parse_error: int = 0

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "records_read": self.records_read,
            "candidates_produced": self.candidates_produced,
            "ingested": self.ingested,
            "blocked": self.blocked,
            "duplicates": self.duplicates,
            "errors": self.errors,
            "skipped_empty_text": self.skipped_empty_text,
            "skipped_no_text_field": self.skipped_no_text_field,
            "skipped_parse_error": self.skipped_parse_error,
        }


@dataclass
class IngestStats:
    """Statistics from an ingestion run."""
    # High-level counts
    total_files_processed: int = 0
    total_records_read: int = 0
    total_candidates: int = 0
    total_found: int = 0  # Legacy: same as total_candidates
    ingested: int = 0
    blocked: int = 0
    skipped_duplicate: int = 0
    errors: int = 0

    # Reader-level skip reasons
    skipped_empty_text: int = 0
    skipped_no_text_field: int = 0
    skipped_parse_error: int = 0

    # Block reason breakdown
    blocked_explicit: int = 0
    blocked_minor: int = 0
    blocked_other: int = 0

    # Per-file breakdown
    file_stats: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_files_processed": self.total_files_processed,
            "total_records_read": self.total_records_read,
            "total_candidates": self.total_candidates,
            "total_found": self.total_found,
            "ingested": self.ingested,
            "blocked": self.blocked,
            "skipped_duplicate": self.skipped_duplicate,
            "errors": self.errors,
            "skip_reasons": {
                "empty_text": self.skipped_empty_text,
                "no_text_field": self.skipped_no_text_field,
                "parse_error": self.skipped_parse_error,
            },
            "block_reasons": {
                "explicit": self.blocked_explicit,
                "minor": self.blocked_minor,
                "other": self.blocked_other,
            },
            "file_stats": [f.to_dict() if hasattr(f, 'to_dict') else f for f in self.file_stats],
        }


@dataclass
class IngestResult:
    """Result of a complete ingestion run."""
    run_id: str
    source: str
    input_path: str
    stats: IngestStats
    started_at: datetime
    finished_at: datetime
    status: str  # completed, failed
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "source": self.source,
            "input_path": self.input_path,
            "stats": self.stats.to_dict(),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "status": self.status,
            "error_message": self.error_message,
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        s = self.stats
        lines = [
            f"Run ID: {self.run_id}",
            f"Status: {self.status}",
            f"",
            f"Files processed: {s.total_files_processed}",
            f"Total records read: {s.total_records_read}",
            f"Candidates produced: {s.total_candidates}",
            f"",
            f"Document counts:",
            f"  - Ingested: {s.ingested}",
            f"  - Blocked: {s.blocked}",
            f"  - Duplicates: {s.skipped_duplicate}",
            f"  - Errors: {s.errors}",
            f"",
            f"Skip reasons (reader level):",
            f"  - Empty text: {s.skipped_empty_text}",
            f"  - No text field: {s.skipped_no_text_field}",
            f"  - Parse error: {s.skipped_parse_error}",
        ]
        if s.blocked > 0:
            lines.extend([
                f"",
                f"Block reasons:",
                f"  - Explicit content: {s.blocked_explicit}",
                f"  - Minor-related: {s.blocked_minor}",
                f"  - Other: {s.blocked_other}",
            ])
        return "\n".join(lines)


class EpsteinCorpusIngestor:
    """
    Ingests Epstein corpus documents from local files.

    Usage:
        ingestor = EpsteinCorpusIngestor(session)
        result = await ingestor.ingest_from_directory(
            input_dir=Path("data/raw/epstein"),
            limit=200,
        )
    """

    def __init__(
        self,
        session: AsyncSession,
        sanitizer: Optional[ContentSanitizer] = None,
        max_summary_length: int = 500,
    ):
        """
        Initialize ingestor.

        Args:
            session: Database session for storing documents
            sanitizer: ContentSanitizer instance (uses default if None)
            max_summary_length: Maximum length for sanitized summaries
        """
        self.session = session
        self.sanitizer = sanitizer or get_sanitizer()
        self.max_summary_length = max_summary_length

    async def ingest_from_directory(
        self,
        input_dir: Path,
        limit: int = 200,
        dry_run: bool = False,
        verbose: bool = False,
        sources: Optional[list[str]] = None,
        ignore_samples: bool = False,
    ) -> IngestResult:
        """
        Ingest documents from a directory containing Epstein corpus files.

        Expected structure:
            input_dir/
            ├── kaggle/          -> SOURCE_KAGGLE
            ├── huggingface/     -> SOURCE_HF
            └── epstein_docs/    -> SOURCE_DOCS

        Args:
            input_dir: Root directory containing source subdirectories
            limit: Maximum documents to ingest (0 = no limit)
            dry_run: If True, don't write to database
            verbose: If True, log each document
            sources: List of source names to process (None = all)
            ignore_samples: If True, skip files with 'sample' in name

        Returns:
            IngestResult with statistics
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        stats = IngestStats()

        logger.info(
            "ingestion_started",
            run_id=run_id,
            input_dir=str(input_dir),
            limit=limit,
            dry_run=dry_run,
        )

        try:
            # Build source directories list, filtering by sources param
            all_source_dirs = [
                ("kaggle", input_dir / "kaggle", SOURCE_KAGGLE),
                ("huggingface", input_dir / "huggingface", SOURCE_HF),
                ("epstein_docs", input_dir / "epstein_docs", SOURCE_DOCS),
            ]

            # Filter to requested sources
            if sources:
                source_dirs = [
                    (d, n) for key, d, n in all_source_dirs
                    if key in sources
                ]
            else:
                source_dirs = [(d, n) for key, d, n in all_source_dirs]

            docs_processed = 0
            limit_reached = False

            for source_dir, source_name in source_dirs:
                if limit_reached:
                    break
                if not source_dir.exists():
                    logger.debug("source_dir_not_found", path=str(source_dir))
                    continue

                # Process files individually for per-file stats
                for file_path in sorted(source_dir.glob("**/*")):
                    # Skip sample files if requested
                    if ignore_samples and "sample" in file_path.name.lower():
                        logger.debug("skipping_sample_file", path=str(file_path))
                        continue
                    if limit_reached:
                        break
                    if not file_path.is_file():
                        continue

                    suffix = file_path.suffix.lower()
                    if suffix not in [".csv", ".json", ".jsonl", ".txt", ".parquet"]:
                        continue

                    # Create per-file stats tracker
                    file_stats = FileStats(
                        file_path=str(file_path),
                        file_type=suffix[1:],  # Remove the dot
                    )

                    # Read documents from this file
                    if suffix == ".csv":
                        docs_iter = read_csv_documents(file_path)
                    elif suffix == ".json":
                        docs_iter = read_json_documents(file_path)
                    elif suffix == ".jsonl":
                        docs_iter = read_jsonl_documents(file_path)
                    elif suffix == ".txt":
                        docs_iter = read_text_documents(file_path)
                    elif suffix == ".parquet":
                        docs_iter = read_parquet_documents(file_path)
                    else:
                        continue

                    # Process documents from this file
                    for doc in docs_iter:
                        if limit > 0 and docs_processed >= limit:
                            limit_reached = True
                            break

                        stats.total_found += 1
                        stats.total_candidates += 1
                        file_stats.candidates_produced += 1

                        result = await self._process_document(
                            doc=doc,
                            source=source_name,
                            dry_run=dry_run,
                            verbose=verbose,
                        )

                        if result == "ingested":
                            stats.ingested += 1
                            file_stats.ingested += 1
                        elif result == "blocked":
                            stats.blocked += 1
                            file_stats.blocked += 1
                        elif result == "blocked_explicit":
                            stats.blocked += 1
                            stats.blocked_explicit += 1
                            file_stats.blocked += 1
                        elif result == "blocked_minor":
                            stats.blocked += 1
                            stats.blocked_minor += 1
                            file_stats.blocked += 1
                        elif result == "duplicate":
                            stats.skipped_duplicate += 1
                            file_stats.duplicates += 1
                        elif result == "error":
                            stats.errors += 1
                            file_stats.errors += 1

                        docs_processed += 1

                    # Get reader-level stats and merge
                    reader_stats = get_current_file_stats()
                    if reader_stats:
                        file_stats.records_read = reader_stats.records_read
                        file_stats.skipped_empty_text = reader_stats.skipped_empty_text
                        file_stats.skipped_no_text_field = reader_stats.skipped_no_text_field
                        file_stats.skipped_parse_error = reader_stats.skipped_parse_error

                        # Aggregate to total stats
                        stats.total_records_read += reader_stats.records_read
                        stats.skipped_empty_text += reader_stats.skipped_empty_text
                        stats.skipped_no_text_field += reader_stats.skipped_no_text_field
                        stats.skipped_parse_error += reader_stats.skipped_parse_error

                    stats.total_files_processed += 1
                    stats.file_stats.append(file_stats)

                    # Log per-file summary
                    logger.info(
                        "file_processed",
                        file_path=str(file_path),
                        records_read=file_stats.records_read,
                        candidates=file_stats.candidates_produced,
                        ingested=file_stats.ingested,
                        blocked=file_stats.blocked,
                        duplicates=file_stats.duplicates,
                    )

            # Log ingestion run to database
            if not dry_run:
                await self._log_ingestion_run(
                    run_id=run_id,
                    source="epstein_corpus",
                    input_path=str(input_dir),
                    stats=stats,
                    started_at=started_at,
                    status="completed",
                )

            finished_at = datetime.now(timezone.utc)
            logger.info(
                "ingestion_completed",
                run_id=run_id,
                stats=stats.to_dict(),
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

            return IngestResult(
                run_id=run_id,
                source="epstein_corpus",
                input_path=str(input_dir),
                stats=stats,
                started_at=started_at,
                finished_at=finished_at,
                status="completed",
            )

        except Exception as e:
            finished_at = datetime.now(timezone.utc)
            logger.error(
                "ingestion_failed",
                run_id=run_id,
                error=str(e),
            )

            if not dry_run:
                await self._log_ingestion_run(
                    run_id=run_id,
                    source="epstein_corpus",
                    input_path=str(input_dir),
                    stats=stats,
                    started_at=started_at,
                    status="failed",
                    error_message=str(e),
                )

            return IngestResult(
                run_id=run_id,
                source="epstein_corpus",
                input_path=str(input_dir),
                stats=stats,
                started_at=started_at,
                finished_at=finished_at,
                status="failed",
                error_message=str(e),
            )

    async def _process_document(
        self,
        doc: dict,
        source: str,
        dry_run: bool,
        verbose: bool,
    ) -> str:
        """
        Process a single document.

        Returns:
            Status string: "ingested", "blocked", "blocked_explicit",
                          "blocked_minor", "duplicate", "error"
        """
        try:
            text = doc.get("text", "")
            doc_id = doc.get("doc_id", "")
            content_hash = doc.get("content_hash", "")

            if not text or not doc_id:
                return "error"

            # Check for duplicate
            if not dry_run:
                existing = await self._check_duplicate(source, doc_id, content_hash)
                if existing:
                    if verbose:
                        logger.debug("document_duplicate", doc_id=doc_id)
                    return "duplicate"

            # Sanitize content
            result = self.sanitizer.sanitize(text, doc_id=doc_id)

            if result.status == SanitizationAction.BLOCKED:
                if verbose:
                    logger.info(
                        "document_blocked",
                        doc_id=doc_id,
                        reason=result.block_reason,
                    )

                # Categorize block reason
                reason = (result.block_reason or "").lower()
                if "minor" in reason or "child" in reason or "underage" in reason:
                    return "blocked_minor"
                elif "sexual" in reason or "explicit" in reason:
                    return "blocked_explicit"
                else:
                    return "blocked"

            # Generate sanitized summary
            sanitized_summary = self.sanitizer.extract_safe_summary(
                text,
                max_length=self.max_summary_length,
                doc_id=doc_id,
            )

            if not sanitized_summary:
                return "blocked"

            # Store document
            if not dry_run:
                await self._store_document(
                    source=source,
                    doc_id=doc_id,
                    content_hash=content_hash,
                    sanitized_summary=sanitized_summary,
                    sanitization_result=result,
                    metadata=doc.get("metadata", {}),
                    source_path=doc.get("source_path"),
                )

            if verbose:
                logger.info(
                    "document_ingested",
                    doc_id=doc_id,
                    status=result.status.value,
                    summary_length=len(sanitized_summary),
                )

            return "ingested"

        except Exception as e:
            logger.error(
                "document_process_error",
                doc_id=doc.get("doc_id", "unknown"),
                error=str(e),
            )
            return "error"

    async def _check_duplicate(
        self,
        source: str,
        doc_id: str,
        content_hash: str,
    ) -> bool:
        """Check if document already exists in database."""
        query = text("""
            SELECT 1 FROM knowledge_documents
            WHERE (source = :source AND doc_id = :doc_id)
               OR content_hash = :content_hash
            LIMIT 1
        """)

        result = await self.session.execute(
            query,
            {"source": source, "doc_id": doc_id, "content_hash": content_hash}
        )
        return result.fetchone() is not None

    async def _store_document(
        self,
        source: str,
        doc_id: str,
        content_hash: str,
        sanitized_summary: str,
        sanitization_result,
        metadata: dict,
        source_path: Optional[str],
    ) -> None:
        """Store document in database."""
        import json

        # Only store raw_text if fully clean (no redactions)
        raw_text = None
        if sanitization_result.status == SanitizationAction.CLEAN:
            # Even then, prefer not storing raw for privacy
            pass  # raw_text stays None

        query = text("""
            INSERT INTO knowledge_documents (
                source, doc_id, content_hash,
                sanitized_summary, raw_text,
                sanitization_status, sanitization_log,
                source_path, metadata_json,
                created_at, updated_at
            ) VALUES (
                :source, :doc_id, :content_hash,
                :sanitized_summary, :raw_text,
                :sanitization_status, :sanitization_log,
                :source_path, :metadata_json,
                NOW(), NOW()
            )
            ON CONFLICT (source, doc_id) DO UPDATE SET
                content_hash = :content_hash,
                sanitized_summary = :sanitized_summary,
                sanitization_status = :sanitization_status,
                sanitization_log = :sanitization_log,
                updated_at = NOW()
        """)

        await self.session.execute(
            query,
            {
                "source": source,
                "doc_id": doc_id,
                "content_hash": content_hash,
                "sanitized_summary": sanitized_summary,
                "raw_text": raw_text,
                "sanitization_status": sanitization_result.status.value,
                "sanitization_log": json.dumps(sanitization_result.to_dict()),
                "source_path": source_path,
                "metadata_json": json.dumps(metadata) if metadata else None,
            }
        )
        await self.session.commit()

    async def _log_ingestion_run(
        self,
        run_id: str,
        source: str,
        input_path: str,
        stats: IngestStats,
        started_at: datetime,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Log ingestion run to database."""
        import json

        # Serialize detailed stats (without file_stats to keep size reasonable)
        stats_summary = {
            "total_files_processed": stats.total_files_processed,
            "total_records_read": stats.total_records_read,
            "total_candidates": stats.total_candidates,
            "ingested": stats.ingested,
            "blocked": stats.blocked,
            "skipped_duplicate": stats.skipped_duplicate,
            "errors": stats.errors,
            "skip_reasons": {
                "empty_text": stats.skipped_empty_text,
                "no_text_field": stats.skipped_no_text_field,
                "parse_error": stats.skipped_parse_error,
            },
            "block_reasons": {
                "explicit": stats.blocked_explicit,
                "minor": stats.blocked_minor,
                "other": stats.blocked_other,
            },
        }

        # Store file stats separately if there are few files
        if len(stats.file_stats) <= 20:
            stats_summary["file_stats"] = [
                f.to_dict() if hasattr(f, 'to_dict') else f
                for f in stats.file_stats
            ]

        # Note: We store detailed stats as JSON in error_message when no error
        # In future, add a stats_json column
        detail_json = json.dumps(stats_summary) if not error_message else error_message

        query = text("""
            INSERT INTO corpus_ingestion_log (
                run_id, source, input_path,
                total_docs, docs_ingested, docs_blocked, docs_skipped,
                started_at, finished_at, status, error_message
            ) VALUES (
                :run_id, :source, :input_path,
                :total_docs, :docs_ingested, :docs_blocked, :docs_skipped,
                :started_at, NOW(), :status, :error_message
            )
        """)

        await self.session.execute(
            query,
            {
                "run_id": run_id,
                "source": source,
                "input_path": input_path,
                "total_docs": stats.total_records_read,  # Use total records read
                "docs_ingested": stats.ingested,
                "docs_blocked": stats.blocked,
                "docs_skipped": stats.skipped_duplicate,
                "started_at": started_at,
                "status": status,
                "error_message": detail_json,
            }
        )
        await self.session.commit()


async def get_corpus_status(session: AsyncSession) -> dict:
    """
    Get current status of Epstein corpus ingestion.

    Returns counts, last ingestion time, and detailed last run stats.
    """
    import json

    # Get document counts by status
    count_query = text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE sanitization_status = 'clean') as clean,
            COUNT(*) FILTER (WHERE sanitization_status = 'redacted') as redacted,
            COUNT(*) FILTER (WHERE sanitization_status = 'blocked') as blocked
        FROM knowledge_documents
        WHERE source IN ('kaggle_epstein_ranker', 'hf_epstein_index', 'epstein_docs')
    """)

    result = await session.execute(count_query)
    counts = result.fetchone()

    # Get last ingestion info including detailed stats
    last_ingest_query = text("""
        SELECT run_id, started_at, finished_at, status,
               total_docs, docs_ingested, docs_blocked, docs_skipped,
               error_message
        FROM corpus_ingestion_log
        WHERE source = 'epstein_corpus'
        ORDER BY started_at DESC
        LIMIT 1
    """)

    result = await session.execute(last_ingest_query)
    last_ingest = result.fetchone()

    # Parse detailed stats from error_message if it's JSON (not an actual error)
    last_run_details = None
    if last_ingest and last_ingest.error_message:
        try:
            last_run_details = json.loads(last_ingest.error_message)
        except (json.JSONDecodeError, TypeError):
            # It's an actual error message, not JSON stats
            pass

    # Build response with detailed stats
    last_ingest_data = None
    if last_ingest:
        last_ingest_data = {
            "run_id": str(last_ingest.run_id),
            "started_at": last_ingest.started_at.isoformat(),
            "finished_at": last_ingest.finished_at.isoformat() if last_ingest.finished_at else None,
            "status": last_ingest.status,
            # Basic counts from columns
            "total_docs": last_ingest.total_docs,
            "docs_ingested": last_ingest.docs_ingested,
            "docs_blocked": last_ingest.docs_blocked,
            "docs_skipped": last_ingest.docs_skipped,
        }
        # Add detailed stats if available
        if last_run_details:
            last_ingest_data["details"] = {
                "total_files_processed": last_run_details.get("total_files_processed", 0),
                "total_records_read": last_run_details.get("total_records_read", 0),
                "total_candidates": last_run_details.get("total_candidates", 0),
                "skip_reasons": last_run_details.get("skip_reasons", {}),
                "block_reasons": last_run_details.get("block_reasons", {}),
                "file_stats": last_run_details.get("file_stats", []),
            }

    return {
        "documents": {
            "total": counts.total if counts else 0,
            "clean": counts.clean if counts else 0,
            "redacted": counts.redacted if counts else 0,
            "blocked": counts.blocked if counts else 0,
        },
        "last_ingest": last_ingest_data,
    }


async def get_corpus_samples(
    session: AsyncSession,
    limit: int = 20,
) -> list[dict]:
    """
    Get sample sanitized summaries for admin review.

    Returns only sanitized_summary and basic metadata.
    Never returns raw text or blocked content.
    """
    query = text("""
        SELECT
            id, source, doc_id, sanitized_summary,
            sanitization_status, created_at
        FROM knowledge_documents
        WHERE source IN ('kaggle_epstein_ranker', 'hf_epstein_index', 'epstein_docs')
          AND sanitization_status IN ('clean', 'redacted')
          AND sanitized_summary IS NOT NULL
        ORDER BY RANDOM()
        LIMIT :limit
    """)

    result = await session.execute(query, {"limit": limit})
    rows = result.fetchall()

    return [
        {
            "id": str(row.id),
            "source": row.source,
            "doc_id": row.doc_id,
            "sanitized_summary": row.sanitized_summary,
            "sanitization_status": row.sanitization_status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
