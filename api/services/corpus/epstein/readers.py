"""
File format readers for Epstein corpus ingestion.

Supports:
- CSV files
- JSON files (single object or array)
- JSONL files (newline-delimited JSON)
- Plain text files
- Parquet files (optional, requires pyarrow)

All readers yield document dictionaries with at least:
- text: The document content
- doc_id: A stable identifier (from file or generated)
- metadata: Additional fields from source
"""

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class FileReadStats:
    """Statistics from reading a single file."""
    file_path: str = ""
    file_type: str = ""
    records_read: int = 0
    candidates_produced: int = 0
    skipped_empty_text: int = 0
    skipped_no_text_field: int = 0
    skipped_parse_error: int = 0
    skipped_not_dict: int = 0

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "records_read": self.records_read,
            "candidates_produced": self.candidates_produced,
            "skipped_empty_text": self.skipped_empty_text,
            "skipped_no_text_field": self.skipped_no_text_field,
            "skipped_parse_error": self.skipped_parse_error,
            "skipped_not_dict": self.skipped_not_dict,
        }


# Global stats collector for current read operation
_current_file_stats: Optional[FileReadStats] = None


def get_current_file_stats() -> Optional[FileReadStats]:
    """Get stats from the current/last file read operation."""
    return _current_file_stats


def reset_file_stats():
    """Reset the current file stats."""
    global _current_file_stats
    _current_file_stats = None

# Parquet support is optional
try:
    import pyarrow.parquet as pq
    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False


def generate_doc_id(text: str, source_path: str) -> str:
    """Generate stable doc_id from content hash."""
    content = f"{source_path}:{text[:1000]}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def generate_content_hash(text: str) -> str:
    """Generate SHA256 hash of full content for deduplication."""
    return hashlib.sha256(text.encode()).hexdigest()


def read_csv_documents(
    file_path: Path,
    text_column: Optional[str] = None,
    id_column: Optional[str] = None,
) -> Iterator[dict]:
    """
    Read documents from a CSV file.

    Args:
        file_path: Path to CSV file
        text_column: Column name containing document text (auto-detected if None)
        id_column: Column name containing document ID (auto-generated if None)

    Yields:
        Document dictionaries with text, doc_id, and metadata
    """
    global _current_file_stats
    _current_file_stats = FileReadStats(file_path=str(file_path), file_type="csv")
    stats = _current_file_stats

    logger.info("reading_csv", path=str(file_path))

    # Common text column names to auto-detect
    TEXT_COLUMNS = ["text", "content", "body", "document", "summary", "description"]
    ID_COLUMNS = ["id", "doc_id", "document_id", "file_id", "name"]

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            # Auto-detect text column
            if text_column is None:
                for col in TEXT_COLUMNS:
                    if col in headers:
                        text_column = col
                        break
                if text_column is None:
                    # Use first column if no match
                    text_column = headers[0] if headers else None

            # Auto-detect ID column
            if id_column is None:
                for col in ID_COLUMNS:
                    if col in headers:
                        id_column = col
                        break

            if text_column is None:
                logger.warning("no_text_column_found", path=str(file_path))
                return

            for row in reader:
                stats.records_read += 1
                text = row.get(text_column, "").strip()
                if not text:
                    stats.skipped_empty_text += 1
                    continue

                doc_id = row.get(id_column, "") if id_column else ""
                if not doc_id:
                    doc_id = generate_doc_id(text, str(file_path))

                stats.candidates_produced += 1
                yield {
                    "text": text,
                    "doc_id": str(doc_id),
                    "content_hash": generate_content_hash(text),
                    "source_path": str(file_path),
                    "metadata": {k: v for k, v in row.items() if k not in [text_column]},
                }

            logger.info(
                "csv_read_complete",
                path=str(file_path),
                records_read=stats.records_read,
                candidates=stats.candidates_produced,
                skipped_empty=stats.skipped_empty_text,
            )

    except Exception as e:
        logger.error("csv_read_error", path=str(file_path), error=str(e))


def read_json_documents(file_path: Path) -> Iterator[dict]:
    """
    Read documents from a JSON file.

    Supports:
    - Array of objects with "text" or "content" field
    - Single object with "documents" or "data" array
    - Single object with text content

    Yields:
        Document dictionaries
    """
    global _current_file_stats
    _current_file_stats = FileReadStats(file_path=str(file_path), file_type="json")
    stats = _current_file_stats

    logger.info("reading_json", path=str(file_path))

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        # Handle array of documents
        if isinstance(data, list):
            logger.info("json_array_found", path=str(file_path), count=len(data))
            for i, item in enumerate(data):
                yield from _extract_document_with_stats(item, file_path, i, stats)
            _log_json_complete(file_path, stats)
            return

        # Handle object with documents array
        if isinstance(data, dict):
            for key in ["documents", "data", "items", "records", "analyses"]:
                if key in data and isinstance(data[key], list):
                    logger.info("json_nested_array_found", path=str(file_path), key=key, count=len(data[key]))
                    for i, item in enumerate(data[key]):
                        yield from _extract_document_with_stats(item, file_path, i, stats)
                    _log_json_complete(file_path, stats)
                    return

            # Single document object
            stats.records_read = 1
            yield from _extract_document_with_stats(data, file_path, 0, stats)
            _log_json_complete(file_path, stats)

    except json.JSONDecodeError as e:
        stats.skipped_parse_error += 1
        logger.error("json_parse_error", path=str(file_path), error=str(e))
    except Exception as e:
        logger.error("json_read_error", path=str(file_path), error=str(e))


def _log_json_complete(file_path: Path, stats: FileReadStats):
    """Log completion of JSON file read."""
    logger.info(
        "json_read_complete",
        path=str(file_path),
        records_read=stats.records_read,
        candidates=stats.candidates_produced,
        skipped_empty=stats.skipped_empty_text,
        skipped_no_field=stats.skipped_no_text_field,
        skipped_not_dict=stats.skipped_not_dict,
    )


def _extract_document(item: dict, file_path: Path, index: int) -> Iterator[dict]:
    """Extract document from a dictionary item (legacy, no stats)."""
    yield from _extract_document_with_stats(item, file_path, index, None)


def _extract_document_with_stats(
    item: dict, file_path: Path, index: int, stats: Optional[FileReadStats]
) -> Iterator[dict]:
    """Extract document from a dictionary item with stats tracking."""
    if stats:
        stats.records_read += 1

    if not isinstance(item, dict):
        if stats:
            stats.skipped_not_dict += 1
        return

    # Find text field - check both top-level and nested structures
    text = None

    # First, check for nested analysis object (GitHub export format: item.analysis.summary)
    if "analysis" in item and isinstance(item["analysis"], dict):
        analysis = item["analysis"]
        # Prefer summary, then significance, then combine both
        if "summary" in analysis and analysis["summary"]:
            text = str(analysis["summary"]).strip()
        elif "significance" in analysis and analysis["significance"]:
            text = str(analysis["significance"]).strip()
        # If both exist, combine them
        if not text and "summary" in analysis and "significance" in analysis:
            parts = []
            if analysis.get("significance"):
                parts.append(str(analysis["significance"]).strip())
            if analysis.get("summary"):
                parts.append(str(analysis["summary"]).strip())
            if parts:
                text = " ".join(parts)

    # If no nested analysis, check top-level fields
    if not text:
        for key in ["text", "content", "body", "document", "summary", "description", "details"]:
            if key in item and item[key] and isinstance(item[key], str):
                text = str(item[key]).strip()
                break

    if not text:
        if stats:
            stats.skipped_no_text_field += 1
        return

    if len(text) < 10:  # Skip very short texts
        if stats:
            stats.skipped_empty_text += 1
        return

    # Find ID field
    doc_id = None
    for key in ["id", "doc_id", "document_id", "document_number", "name", "file_id", "entry_id"]:
        if key in item and item[key]:
            doc_id = str(item[key])
            break

    if not doc_id:
        doc_id = generate_doc_id(text, f"{file_path}:{index}")

    if stats:
        stats.candidates_produced += 1

    # Build metadata - include analysis fields but not the full text
    metadata = {}
    for k, v in item.items():
        if k in ["text", "content", "body", "details"]:
            continue
        if k == "analysis" and isinstance(v, dict):
            # Include analysis metadata but not the text fields
            metadata["document_type"] = v.get("document_type")
            metadata["key_topics"] = v.get("key_topics")
            metadata["key_people"] = v.get("key_people")
        else:
            metadata[k] = v

    yield {
        "text": text,
        "doc_id": doc_id,
        "content_hash": generate_content_hash(text),
        "source_path": str(file_path),
        "metadata": metadata,
    }


def read_jsonl_documents(file_path: Path) -> Iterator[dict]:
    """
    Read documents from a JSONL (newline-delimited JSON) file.

    Each line is a JSON object with text content.

    Yields:
        Document dictionaries
    """
    global _current_file_stats
    _current_file_stats = FileReadStats(file_path=str(file_path), file_type="jsonl")
    stats = _current_file_stats

    logger.info("reading_jsonl", path=str(file_path))

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            line_num = 0
            for line in f:
                line_num += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    item = json.loads(line)
                    yield from _extract_document_with_stats(item, file_path, line_num, stats)
                except json.JSONDecodeError:
                    stats.skipped_parse_error += 1
                    logger.debug("jsonl_line_invalid", path=str(file_path), line=line_num)
                    continue

            logger.info(
                "jsonl_read_complete",
                path=str(file_path),
                lines=line_num,
                records_read=stats.records_read,
                candidates=stats.candidates_produced,
                skipped_empty=stats.skipped_empty_text,
                skipped_no_field=stats.skipped_no_text_field,
                skipped_parse=stats.skipped_parse_error,
            )

    except Exception as e:
        logger.error("jsonl_read_error", path=str(file_path), error=str(e))


def read_text_documents(file_path: Path) -> Iterator[dict]:
    """
    Read a single document from a plain text file.

    The entire file content becomes one document.

    Yields:
        Single document dictionary
    """
    logger.info("reading_text", path=str(file_path))

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read().strip()

        if not text:
            return

        doc_id = generate_doc_id(text, str(file_path))

        yield {
            "text": text,
            "doc_id": doc_id,
            "content_hash": generate_content_hash(text),
            "source_path": str(file_path),
            "metadata": {
                "filename": file_path.name,
                "size_bytes": file_path.stat().st_size,
            },
        }

    except Exception as e:
        logger.error("text_read_error", path=str(file_path), error=str(e))


def read_parquet_documents(
    file_path: Path,
    text_column: Optional[str] = None,
    id_column: Optional[str] = None,
    batch_size: int = 1000,
) -> Iterator[dict]:
    """
    Read documents from a Parquet file.

    Requires pyarrow to be installed.

    Args:
        file_path: Path to Parquet file
        text_column: Column name containing document text
        id_column: Column name containing document ID
        batch_size: Number of rows to process at once

    Yields:
        Document dictionaries
    """
    if not PARQUET_AVAILABLE:
        logger.warning(
            "parquet_not_available",
            path=str(file_path),
            message="Install pyarrow to read Parquet files: pip install pyarrow"
        )
        return

    logger.info("reading_parquet", path=str(file_path))

    TEXT_COLUMNS = ["text", "content", "body", "document", "summary"]
    ID_COLUMNS = ["id", "doc_id", "document_id", "name"]

    try:
        table = pq.read_table(file_path)
        columns = table.column_names

        # Auto-detect columns
        if text_column is None:
            for col in TEXT_COLUMNS:
                if col in columns:
                    text_column = col
                    break
            if text_column is None:
                text_column = columns[0] if columns else None

        if id_column is None:
            for col in ID_COLUMNS:
                if col in columns:
                    id_column = col
                    break

        if text_column is None:
            logger.warning("no_text_column_in_parquet", path=str(file_path))
            return

        # Process in batches
        total_rows = 0
        for batch in table.to_batches(max_chunksize=batch_size):
            df = batch.to_pandas()

            for idx, row in df.iterrows():
                text = str(row.get(text_column, "")).strip()
                if not text:
                    continue

                doc_id = str(row.get(id_column, "")) if id_column else ""
                if not doc_id:
                    doc_id = generate_doc_id(text, f"{file_path}:{idx}")

                total_rows += 1
                yield {
                    "text": text,
                    "doc_id": doc_id,
                    "content_hash": generate_content_hash(text),
                    "source_path": str(file_path),
                    "metadata": {k: str(v) for k, v in row.items() if k not in [text_column]},
                }

        logger.info("parquet_read_complete", path=str(file_path), rows=total_rows)

    except Exception as e:
        logger.error("parquet_read_error", path=str(file_path), error=str(e))


def read_documents_from_directory(
    directory: Path,
    recursive: bool = True,
) -> Iterator[dict]:
    """
    Read all supported documents from a directory.

    Args:
        directory: Directory path
        recursive: Whether to search subdirectories

    Yields:
        Document dictionaries from all files
    """
    if not directory.exists():
        logger.warning("directory_not_found", path=str(directory))
        return

    pattern = "**/*" if recursive else "*"

    for file_path in directory.glob(pattern):
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()

        if suffix == ".csv":
            yield from read_csv_documents(file_path)
        elif suffix == ".json":
            yield from read_json_documents(file_path)
        elif suffix == ".jsonl":
            yield from read_jsonl_documents(file_path)
        elif suffix == ".txt":
            yield from read_text_documents(file_path)
        elif suffix == ".parquet":
            yield from read_parquet_documents(file_path)
        # Skip unknown formats silently
