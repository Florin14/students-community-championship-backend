"""Add the optional number of spectators to matches.

Revision ID: e94b3128f560
Revises: c31a94e0d672
"""
from alembic import op
import sqlalchemy as sa

revision = "e94b3128f560"
down_revision = "c31a94e0d672"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("matches") as batch_op:
        batch_op.add_column(sa.Column("audience", sa.Integer(), nullable=True))
        batch_op.create_check_constraint("ck_matches_audience_nonnegative", "audience >= 0")


def downgrade():
    with op.batch_alter_table("matches") as batch_op:
        batch_op.drop_constraint("ck_matches_audience_nonnegative", type_="check")
        batch_op.drop_column("audience")
