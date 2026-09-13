"""add multi-tenancy: orgs, workspaces, workspace_members

Revision ID: 29ffa6203105
Revises: da0ae8433124
Create Date: 2026-09-13 03:14:03.431854

WHY THIS MIGRATION IS HAND-WRITTEN, NOT PURE AUTOGENERATE:
    Autogenerate wanted to add `users.org_id` and `datasets.workspace_id`
    directly as NOT NULL, which fails against tables that already have
    rows (this database has 3 users / 8 datasets at the time this
    migration was written) — Postgres rejects a NOT NULL column add with
    no default on a non-empty table. The real sequence is: add the
    column nullable, backfill every existing row, then tighten to NOT
    NULL. Autogenerate also left the new foreign keys unnamed, which
    would have made downgrade() unrunnable (drop_constraint(None, ...)
    is not valid) — every constraint below is named explicitly instead.

    Backfill policy (see docs/ADR.md ADR-011): one personal org +
    default workspace per existing user, not one shared org for
    everyone. This preserves current per-user data isolation exactly —
    two existing users who currently can't see each other's datasets
    still can't, after this migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29ffa6203105'
down_revision: Union[str, Sequence[str], None] = 'da0ae8433124'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New tables ---
    op.create_table(
        'orgs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_orgs_id'), 'orgs', ['id'], unique=False)

    op.create_table(
        'workspaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['orgs.id'], name='fk_workspaces_org_id_orgs'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workspaces_id'), 'workspaces', ['id'], unique=False)

    op.create_table(
        'workspace_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_workspace_members_user_id_users'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_workspace_members_workspace_id_workspaces'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'workspace_id', name='uq_workspace_member'),
    )
    op.create_index(op.f('ix_workspace_members_id'), 'workspace_members', ['id'], unique=False)

    # --- New columns on existing tables — nullable until backfilled below ---
    op.add_column('datasets', sa.Column('workspace_id', sa.Integer(), nullable=True))
    op.add_column('datasets', sa.Column('sheet_name', sa.String(), nullable=True))
    op.create_foreign_key(
        'fk_datasets_workspace_id_workspaces', 'datasets', 'workspaces', ['workspace_id'], ['id']
    )

    op.add_column('users', sa.Column('org_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_users_org_id_orgs', 'users', 'orgs', ['org_id'], ['id'])

    # --- Data backfill ---
    # Lightweight table proxies, not the live ORM models — a migration
    # should describe exactly the schema shape at this point in history,
    # independent of how app/models/*.py looks today or in the future.
    bind = op.get_bind()

    orgs_t = sa.table('orgs', sa.column('id', sa.Integer), sa.column('name', sa.String))
    workspaces_t = sa.table(
        'workspaces',
        sa.column('id', sa.Integer),
        sa.column('org_id', sa.Integer),
        sa.column('name', sa.String),
    )
    workspace_members_t = sa.table(
        'workspace_members',
        sa.column('id', sa.Integer),
        sa.column('user_id', sa.Integer),
        sa.column('workspace_id', sa.Integer),
        sa.column('role', sa.String),
    )
    users_t = sa.table(
        'users', sa.column('id', sa.Integer), sa.column('email', sa.String), sa.column('org_id', sa.Integer)
    )
    datasets_t = sa.table(
        'datasets', sa.column('id', sa.Integer), sa.column('user_id', sa.Integer), sa.column('workspace_id', sa.Integer)
    )

    existing_users = bind.execute(sa.select(users_t.c.id, users_t.c.email)).fetchall()

    for user_id, email in existing_users:
        org_id = bind.execute(
            orgs_t.insert().values(name=f"{email}'s Organization").returning(orgs_t.c.id)
        ).scalar_one()

        workspace_id = bind.execute(
            workspaces_t.insert().values(org_id=org_id, name="Default").returning(workspaces_t.c.id)
        ).scalar_one()

        bind.execute(
            workspace_members_t.insert().values(user_id=user_id, workspace_id=workspace_id, role="owner")
        )

        bind.execute(users_t.update().where(users_t.c.id == user_id).values(org_id=org_id))

        bind.execute(
            datasets_t.update().where(datasets_t.c.user_id == user_id).values(workspace_id=workspace_id)
        )

    # --- Now that every row has a value, tighten to the real constraint ---
    op.alter_column('users', 'org_id', nullable=False)
    op.alter_column('datasets', 'workspace_id', nullable=False)


def downgrade() -> None:
    op.drop_constraint('fk_users_org_id_orgs', 'users', type_='foreignkey')
    op.drop_column('users', 'org_id')

    op.drop_constraint('fk_datasets_workspace_id_workspaces', 'datasets', type_='foreignkey')
    op.drop_column('datasets', 'sheet_name')
    op.drop_column('datasets', 'workspace_id')

    op.drop_index(op.f('ix_workspace_members_id'), table_name='workspace_members')
    op.drop_table('workspace_members')
    op.drop_index(op.f('ix_workspaces_id'), table_name='workspaces')
    op.drop_table('workspaces')
    op.drop_index(op.f('ix_orgs_id'), table_name='orgs')
    op.drop_table('orgs')
