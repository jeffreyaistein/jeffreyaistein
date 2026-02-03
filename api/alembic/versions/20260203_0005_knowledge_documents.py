"""Add knowledge_documents table for corpus ingestion

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-03 04:00:00.000000

This table stores sanitized knowledge documents from external corpora:
- Epstein corpus (community datasets, sanitized)
- Future knowledge sources

Only sanitized_summary is stored for most documents.
Raw text stored only for fully clean documents (rare).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # Knowledge Documents (sanitized corpus storage)
    # ===========================================
    op.create_table(
        'knowledge_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # Source identification
        sa.Column('source', sa.String(100), nullable=False),  # kaggle_epstein_ranker, hf_epstein_index, epstein_docs
        sa.Column('doc_id', sa.String(255), nullable=False),  # Stable identifier from source or content hash
        sa.Column('content_hash', sa.String(64), nullable=False),  # SHA256 for deduplication

        # Document metadata
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('doc_type', sa.String(50), nullable=True),  # deposition, flight_log, testimony, etc.
        sa.Column('source_path', sa.String(1000), nullable=True),  # Original file path
        sa.Column('source_url', sa.String(1000), nullable=True),  # Original URL if known

        # Content (sanitized only)
        sa.Column('sanitized_summary', sa.Text, nullable=True),  # High-level safe summary
        sa.Column('raw_text', sa.Text, nullable=True),  # Only stored if fully clean (rare)

        # Sanitization info
        sa.Column('sanitization_status', sa.String(20), nullable=False),  # clean, redacted, blocked
        sa.Column('sanitization_log', postgresql.JSONB, nullable=True),  # Actions taken
        sa.Column('block_reason', sa.String(255), nullable=True),  # Why blocked (if blocked)

        # Metadata
        sa.Column('metadata_json', postgresql.JSONB, nullable=True),  # Extensible metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )

    # Unique constraint on source + doc_id
    op.create_unique_constraint(
        'uq_knowledge_documents_source_doc_id',
        'knowledge_documents',
        ['source', 'doc_id']
    )

    # Index on content_hash for deduplication lookups
    op.create_index(
        'ix_knowledge_documents_content_hash',
        'knowledge_documents',
        ['content_hash']
    )

    # Index on source for filtering
    op.create_index(
        'ix_knowledge_documents_source',
        'knowledge_documents',
        ['source']
    )

    # Index on sanitization_status for filtering
    op.create_index(
        'ix_knowledge_documents_status',
        'knowledge_documents',
        ['sanitization_status']
    )

    # ===========================================
    # Corpus Ingestion Log (audit trail)
    # ===========================================
    op.create_table(
        'corpus_ingestion_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),  # Groups docs from same run
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('input_path', sa.String(1000), nullable=True),

        # Counts
        sa.Column('total_docs', sa.Integer, default=0),
        sa.Column('docs_ingested', sa.Integer, default=0),
        sa.Column('docs_blocked', sa.Integer, default=0),
        sa.Column('docs_skipped', sa.Integer, default=0),  # Duplicates

        # Timing
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),

        # Error tracking
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=False),  # running, completed, failed
    )

    op.create_index(
        'ix_corpus_ingestion_log_run_id',
        'corpus_ingestion_log',
        ['run_id']
    )


def downgrade() -> None:
    op.drop_table('corpus_ingestion_log')
    op.drop_table('knowledge_documents')
