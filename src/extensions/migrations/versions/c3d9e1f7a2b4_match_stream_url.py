"""match stream url

Adds `matches.stream_url`: the public broadcast of a match (a YouTube live,
typically), shown on the match page next to the live score. Nullable, no
default - most matches have no stream.

Hand-written: a single nullable column needs nothing from autogenerate, and the
downgrade uses a batch operation so it also works on SQLite (the test
harness fallback has no DROP COLUMN before 3.35).

Revision ID: c3d9e1f7a2b4
Revises: a2be5663eafa
Create Date: 2026-09-12 20:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d9e1f7a2b4'
down_revision = 'a2be5663eafa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'matches', sa.Column('stream_url', sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    with op.batch_alter_table('matches') as batch:
        batch.drop_column('stream_url')
