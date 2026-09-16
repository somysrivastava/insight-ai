"""add column_mappings table

Revision ID: 0f8b5d1de3d4
Revises: 49eddf891c19
Create Date: 2026-09-16 06:16:30.920699

Day 22 — human-readable metadata (display_name/description/unit) per
dataset column, feeding ai_service.py's context for the AI query layer.
No data backfill needed, brand new table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0f8b5d1de3d4'
down_revision: Union[str, Sequence[str], None] = '49eddf891c19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('column_mappings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dataset_id', sa.Integer(), nullable=False),
    sa.Column('column_name', sa.String(), nullable=False),
    sa.Column('display_name', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('unit', sa.String(), nullable=True),
    sa.Column('is_metric', sa.Boolean(), nullable=False),
    sa.Column('is_dimension', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dataset_id', 'column_name', name='uq_column_mapping_dataset_column')
    )
    op.create_index(op.f('ix_column_mappings_id'), 'column_mappings', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_column_mappings_id'), table_name='column_mappings')
    op.drop_table('column_mappings')
