"""Unify stadium staff accounts under the Operator role.

Revision ID: d6a9218f4c73
Revises: b72e640a1c98
"""
from alembic import op

revision = "d6a9218f4c73"
down_revision = "b72e640a1c98"
branch_labels = None
depends_on = None


def upgrade():
    # Keep account IDs, credentials, active/disabled states and audit links.
    # Compare text so an earlier revision can add the old enum value in this
    # same transaction without requiring PostgreSQL to use it as an enum literal.
    op.execute("UPDATE users SET role = 'OPERATOR' WHERE CAST(role AS TEXT) = 'VOLUNTEER'")
    if op.get_bind().dialect.name == "postgresql":
        # PostgreSQL cannot remove a value from an existing enum.
        op.execute("ALTER TYPE platformroles RENAME TO platformroles_before_operator_merge")
        op.execute("CREATE TYPE platformroles AS ENUM ('OPERATOR', 'ADMIN', 'SUPER_ADMIN')")
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE platformroles USING role::text::platformroles")
        op.execute("DROP TYPE platformroles_before_operator_merge")


def downgrade():
    # Older code accepts Operator with the same rights, so leave accounts intact.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE platformroles ADD VALUE IF NOT EXISTS 'VOLUNTEER'")
