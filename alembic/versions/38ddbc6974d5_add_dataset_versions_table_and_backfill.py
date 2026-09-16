"""add dataset_versions table and backfill

Revision ID: 38ddbc6974d5
Revises: 0f8b5d1de3d4
Create Date: 2026-09-16 07:05:00.000000

Day 23 — every existing Dataset row gets a corresponding DatasetVersion
row (version 1, is_current=True) pointing at its current file_path, and
Dataset.current_version_number gets backfilled to 1. Same pattern as
the Day 16 multi-tenancy backfill (ADR-011): lightweight sa.table()
proxies, not the live ORM models, so this migration describes exactly
the schema shape at this point in history.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '38ddbc6974d5'
down_revision: Union[str, Sequence[str], None] = '0f8b5d1de3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('dataset_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dataset_id', sa.Integer(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('file_path', sa.String(), nullable=False),
    sa.Column('row_count', sa.Integer(), nullable=False),
    sa.Column('column_count', sa.Integer(), nullable=False),
    sa.Column('uploaded_by', sa.Integer(), nullable=False),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('change_summary', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dataset_id', 'version_number', name='uq_dataset_version_number')
    )
    op.create_index(op.f('ix_dataset_versions_id'), 'dataset_versions', ['id'], unique=False)

    op.add_column('datasets', sa.Column('current_version_number', sa.Integer(), nullable=True))

    # --- Data backfill ---
    bind = op.get_bind()

    datasets_t = sa.table(
        'datasets',
        sa.column('id', sa.Integer),
        sa.column('user_id', sa.Integer),
        sa.column('file_path', sa.String),
        sa.column('row_count', sa.Integer),
        sa.column('column_count', sa.Integer),
        sa.column('current_version_number', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    dataset_versions_t = sa.table(
        'dataset_versions',
        sa.column('dataset_id', sa.Integer),
        sa.column('version_number', sa.Integer),
        sa.column('file_path', sa.String),
        sa.column('row_count', sa.Integer),
        sa.column('column_count', sa.Integer),
        sa.column('uploaded_by', sa.Integer),
        sa.column('is_current', sa.Boolean),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )

    existing_datasets = bind.execute(
        sa.select(
            datasets_t.c.id,
            datasets_t.c.user_id,
            datasets_t.c.file_path,
            datasets_t.c.row_count,
            datasets_t.c.column_count,
            datasets_t.c.created_at,
        )
    ).fetchall()

    for dataset_id, user_id, file_path, row_count, column_count, created_at in existing_datasets:
        bind.execute(
            dataset_versions_t.insert().values(
                dataset_id=dataset_id,
                version_number=1,
                file_path=file_path,
                row_count=row_count,
                column_count=column_count,
                uploaded_by=user_id,
                is_current=True,
                created_at=created_at,
            )
        )
        bind.execute(
            datasets_t.update().where(datasets_t.c.id == dataset_id).values(current_version_number=1)
        )

    op.alter_column('datasets', 'current_version_number', nullable=False)


def downgrade() -> None:
    op.drop_column('datasets', 'current_version_number')
    op.drop_index(op.f('ix_dataset_versions_id'), table_name='dataset_versions')
    op.drop_table('dataset_versions')
