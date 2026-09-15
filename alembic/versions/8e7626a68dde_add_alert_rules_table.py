"""add alert_rules table

Revision ID: 8e7626a68dde
Revises: 641ed2ccd68d
Create Date: 2026-09-15 20:53:19.763075

Day 20 — monitors one column of one dataset. No data backfill needed,
brand new table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8e7626a68dde'
down_revision: Union[str, Sequence[str], None] = '641ed2ccd68d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('alert_rules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workspace_id', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('dataset_id', sa.Integer(), nullable=False),
    sa.Column('column', sa.String(), nullable=False),
    sa.Column('metric', sa.String(), nullable=False),
    sa.Column('condition', sa.String(), nullable=False),
    sa.Column('threshold', sa.Float(), nullable=False),
    sa.Column('use_statistical', sa.Boolean(), nullable=False),
    sa.Column('z_score_threshold', sa.Float(), nullable=False),
    sa.Column('frequency', sa.String(), nullable=False),
    sa.Column('recipients', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_rules_id'), 'alert_rules', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_alert_rules_id'), table_name='alert_rules')
    op.drop_table('alert_rules')
