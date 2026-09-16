"""add dashboard_pins table

Revision ID: 49eddf891c19
Revises: aac43c57e323
Create Date: 2026-09-16 05:44:32.279203

Day 21 — one pinned result per row (pin_type/source_id/query_params
describe how to re-run it, cached_result holds the last computed
output). Split into a separate migration from dashboards even though
both were introduced together, matching the Day 20 alert_rules/
alert_history numbering precedent. No data backfill needed, brand new
table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '49eddf891c19'
down_revision: Union[str, Sequence[str], None] = 'aac43c57e323'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('dashboard_pins',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dashboard_id', sa.Integer(), nullable=False),
    sa.Column('pinned_by', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('pin_type', sa.String(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('query_params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cached_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['dashboard_id'], ['dashboards.id'], ),
    sa.ForeignKeyConstraint(['pinned_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dashboard_pins_id'), 'dashboard_pins', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dashboard_pins_id'), table_name='dashboard_pins')
    op.drop_table('dashboard_pins')
