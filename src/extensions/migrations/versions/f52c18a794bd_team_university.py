"""Add a team's university separately from its faculty.

Revision ID: f52c18a794bd
Revises: e94b3128f560
"""
from alembic import op
import sqlalchemy as sa

revision = "f52c18a794bd"
down_revision = "e94b3128f560"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("teams", sa.Column("university", sa.String(160), nullable=True))


def downgrade():
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("university")
