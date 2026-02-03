"""Add style_guide_versions table for versioned style guide proposals

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-03 02:30:00.000000

This table tracks style guide versions generated from self-style analysis:
- Each proposal is stored as a version with metadata
- Only ONE version can be active at a time (enforced by partial unique index)
- Activation/deactivation timestamps enable audit trail
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # Style Guide Versions (proposal tracking)
    # ===========================================
    op.create_table(
        'style_guide_versions',
        # Primary key: version_id like "20260203_153045"
        sa.Column('version_id', sa.String(20), primary_key=True),

        # Generation metadata
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(50), nullable=False, server_default='self_style'),
        sa.Column('tweet_count', sa.Integer, nullable=False),

        # File paths (relative to project root)
        sa.Column('md_path', sa.String(255), nullable=False),
        sa.Column('json_path', sa.String(255), nullable=False),

        # Activation state
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),

        # Full metadata as JSONB for extensibility
        sa.Column('metadata_json', postgresql.JSONB, nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Index for listing versions by generation time
    op.create_index('ix_style_guide_versions_generated_at', 'style_guide_versions', ['generated_at'])

    # Index for finding active version quickly
    op.create_index('ix_style_guide_versions_is_active', 'style_guide_versions', ['is_active'])

    # CRITICAL: Partial unique index ensures only ONE active version at a time
    # This is enforced at the database level - no application bugs can violate it
    op.execute("""
        CREATE UNIQUE INDEX ix_style_guide_versions_single_active
        ON style_guide_versions (is_active)
        WHERE is_active = true
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_style_guide_versions_single_active")
    op.drop_index('ix_style_guide_versions_is_active', table_name='style_guide_versions')
    op.drop_index('ix_style_guide_versions_generated_at', table_name='style_guide_versions')
    op.drop_table('style_guide_versions')
