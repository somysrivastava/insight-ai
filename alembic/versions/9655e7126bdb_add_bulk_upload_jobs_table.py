"""add bulk_upload_jobs table

Revision ID: 9655e7126bdb
Revises: 38ddbc6974d5
Create Date: 2026-09-16 18:22:48.496724

Day 24 — tracks one bulk-upload request, updated incrementally as each
file is processed. No data backfill needed, brand new table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9655e7126bdb'
down_revision: Union[str, Sequence[str], None] = '38ddbc6974d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('bulk_upload_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workspace_id', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('total_files', sa.Integer(), nullable=False),
    sa.Column('succeeded', sa.Integer(), nullable=False),
    sa.Column('failed', sa.Integer(), nullable=False),
    sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bulk_upload_jobs_id'), 'bulk_upload_jobs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_bulk_upload_jobs_id'), table_name='bulk_upload_jobs')
    op.drop_table('bulk_upload_jobs')
