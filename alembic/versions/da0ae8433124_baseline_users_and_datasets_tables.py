"""baseline: users and datasets tables

Revision ID: da0ae8433124
Revises:
Create Date: 2026-09-13 03:24:58.432354

WHY THIS MIGRATION EXISTS:
    `users` and `datasets` predate Alembic entirely — they were created
    by app/main.py's Base.metadata.create_all() from Day 5 onward, which
    Day 16 removes in favor of Alembic-managed schema (create_all()
    can't alter existing tables or backfill data, which Day 16's
    multi-tenancy migration needs to do). Without this baseline, a
    genuinely fresh database (a new environment, CI, or — as caught
    while testing this exact migration — a fresh Docker Compose volume)
    has no way to get `users`/`datasets` created at all, since the Day
    16 migration only ever ALTERs them.

    This is the schema exactly as it stood immediately before Day 16 —
    intentionally not "improved" or reconciled with current models.py,
    since a migration should describe a real point in the project's
    history, not the author's current opinion of what the schema should
    have looked like.

    Databases that already had users/datasets from create_all() (i.e.
    any environment that ran the app before Day 16) already satisfy
    this migration's effect; run `alembic stamp da0ae8433124` there
    before `alembic upgrade head` if `alembic_version` isn't already
    past this point.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da0ae8433124'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.create_table(
        'datasets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('column_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_datasets_user_id_users'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_datasets_id'), 'datasets', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_datasets_id'), table_name='datasets')
    op.drop_table('datasets')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
