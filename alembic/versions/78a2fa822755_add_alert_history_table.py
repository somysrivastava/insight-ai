"""add alert_history table

Revision ID: 78a2fa822755
Revises: 8e7626a68dde
Create Date: 2026-09-15 20:53:38.930381

Day 20 — one row per evaluation of a check (threshold or statistical),
not just per trigger. See app/models/alert_history.py and ADR-015 for
why: the statistical check's rolling-window baseline needs every past
value, not a biased sample of only-past-anomalies. No data backfill
needed, brand new table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '78a2fa822755'
down_revision: Union[str, Sequence[str], None] = '8e7626a68dde'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('alert_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('alert_rule_id', sa.Integer(), nullable=False),
    sa.Column('checked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('triggered', sa.Boolean(), nullable=False),
    sa.Column('actual_value', sa.Float(), nullable=False),
    sa.Column('z_score', sa.Float(), nullable=True),
    sa.Column('alert_type', sa.String(), nullable=False),
    sa.Column('email_sent', sa.Boolean(), nullable=False),
    sa.Column('error', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['alert_rule_id'], ['alert_rules.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_history_id'), 'alert_history', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_alert_history_id'), table_name='alert_history')
    op.drop_table('alert_history')
