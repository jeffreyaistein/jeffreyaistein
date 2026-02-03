#!/usr/bin/env python3
"""
Epstein Corpus Ingestion Script

Ingests documents from local files into the knowledge_documents table.
All documents are sanitized before storage.

Usage:
    python scripts/ingest_epstein_corpus.py --input-dir apps/data/raw/epstein
    python scripts/ingest_epstein_corpus.py --input-dir apps/data/raw/epstein --limit 200
    python scripts/ingest_epstein_corpus.py --input-dir apps/data/raw/epstein --dry-run
    python scripts/ingest_epstein_corpus.py --input-dir apps/data/raw/epstein --verbose
    python scripts/ingest_epstein_corpus.py --input-dir apps/data/raw/epstein --sources epstein_docs --ignore-samples --limit 300

Expected directory structure:
    input-dir/
    ├── kaggle/          # Kaggle epstein-ranker dataset files
    ├── huggingface/     # HuggingFace FULL_EPSTEIN_INDEX files
    └── epstein_docs/    # epstein-docs.github.io exports (optional)

Supported file formats:
    - CSV (.csv)
    - JSON (.json)
    - JSONL (.jsonl)
    - Plain text (.txt)
    - Parquet (.parquet) - requires pyarrow

Safety:
    - All documents pass through ContentSanitizer
    - Explicit content is blocked (not stored)
    - Victim identifiers are redacted
    - Only sanitized summaries are stored
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.base import async_session_maker
from services.corpus.epstein import EpsteinCorpusIngestor


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest Epstein corpus from local files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Root directory containing source subdirectories (kaggle/, huggingface/, epstein_docs/)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum documents to ingest (0 = no limit, default: 200)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process documents without writing to database",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log each document processed",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-ingestion of all documents (ignore duplicates)",
    )
    parser.add_argument(
        "--sources",
        type=str,
        default=None,
        help="Comma-separated list of sources to process (e.g., 'epstein_docs,kaggle'). Default: all sources.",
    )
    parser.add_argument(
        "--ignore-samples",
        action="store_true",
        help="Skip files containing 'sample' in the filename",
    )

    args = parser.parse_args()

    # Parse sources filter
    sources_filter = None
    if args.sources:
        sources_filter = [s.strip() for s in args.sources.split(",")]

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        sys.exit(1)

    # Check for source directories
    all_sources = ["kaggle", "huggingface", "epstein_docs"]
    sources_to_process = sources_filter if sources_filter else all_sources

    sources_found = []
    for subdir in sources_to_process:
        subpath = input_dir / subdir
        if subpath.exists():
            file_count = len(list(subpath.glob("*")))
            sources_found.append(f"  - {subdir}: {file_count} files")
        elif sources_filter:
            # User explicitly requested this source but it doesn't exist
            print(f"Warning: Requested source '{subdir}' not found in {input_dir}")

    if not sources_found:
        print(f"Error: No source directories found in {input_dir}")
        if sources_filter:
            print(f"Requested sources: {', '.join(sources_filter)}")
        else:
            print("Expected: kaggle/, huggingface/, and/or epstein_docs/")
        sys.exit(1)

    print("=" * 60)
    print("Epstein Corpus Ingestion")
    print("=" * 60)
    print(f"Input directory: {input_dir}")
    print(f"Limit: {args.limit if args.limit > 0 else 'unlimited'}")
    print(f"Dry run: {args.dry_run}")
    print(f"Verbose: {args.verbose}")
    print(f"Sources filter: {', '.join(sources_to_process) if sources_filter else 'all'}")
    print(f"Ignore samples: {args.ignore_samples}")
    print()
    print("Sources found:")
    for source in sources_found:
        print(source)
    print()

    if args.dry_run:
        print("[DRY RUN] No changes will be written to database")
        print()

    # Run ingestion
    async with async_session_maker() as session:
        ingestor = EpsteinCorpusIngestor(session)
        result = await ingestor.ingest_from_directory(
            input_dir=input_dir,
            limit=args.limit,
            dry_run=args.dry_run,
            verbose=args.verbose,
            sources=sources_filter,
            ignore_samples=args.ignore_samples,
        )

    # Print results
    print()
    print("-" * 60)
    print("Results")
    print("-" * 60)
    print(result.summary())
    print()
    print(f"Duration: {(result.finished_at - result.started_at).total_seconds():.2f}s")

    # Print per-file breakdown
    if result.stats.file_stats:
        print()
        print("-" * 60)
        print("Per-file breakdown:")
        print("-" * 60)
        for fs in result.stats.file_stats:
            print(f"\n  {fs.file_path}")
            print(f"    Records read: {fs.records_read}")
            print(f"    Candidates: {fs.candidates_produced}")
            print(f"    Ingested: {fs.ingested}")
            if fs.blocked > 0:
                print(f"    Blocked: {fs.blocked}")
            if fs.duplicates > 0:
                print(f"    Duplicates: {fs.duplicates}")
            if fs.skipped_empty_text > 0:
                print(f"    Skipped (empty): {fs.skipped_empty_text}")
            if fs.skipped_no_text_field > 0:
                print(f"    Skipped (no text field): {fs.skipped_no_text_field}")

    if result.error_message:
        print()
        print(f"Error: {result.error_message}")

    print()
    print("=" * 60)
    if result.status == "completed" and not args.dry_run:
        print("Ingestion complete. Run admin review before enabling.")
        print()
        print("Next steps:")
        print("  1. Review samples: GET /api/admin/corpus/epstein/samples")
        print("  2. Check status: GET /api/admin/corpus/epstein/status")
        print("  3. Enable (after review): POST /api/admin/corpus/epstein/enable")
    elif args.dry_run:
        print("[DRY RUN] Complete. Remove --dry-run to write to database.")
    else:
        print("Ingestion failed. Check logs for details.")
    print("=" * 60)

    sys.exit(0 if result.status == "completed" else 1)


if __name__ == "__main__":
    asyncio.run(main())
