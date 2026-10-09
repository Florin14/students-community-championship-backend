"""Add an editable competition calendar to each season.

Revision ID: b72e640a1c98
Revises: f52c18a794bd
"""
from alembic import op
import sqlalchemy as sa

revision = "b72e640a1c98"
down_revision = "f52c18a794bd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("seasons", sa.Column("calendar", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade():
    with op.batch_alter_table("seasons") as batch_op:
        batch_op.drop_column("calendar")
