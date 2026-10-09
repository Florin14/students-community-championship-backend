"""Volunteer role, season QR credentials and match attendance.

Revision ID: c31a94e0d672
Revises: a2be5663eafa
"""
from alembic import op
import sqlalchemy as sa

revision = "c31a94e0d672"
down_revision = "a2be5663eafa"
branch_labels = None
depends_on = None

BigIntPK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE platformroles ADD VALUE IF NOT EXISTS 'VOLUNTEER'")

    op.create_table(
        "player_qr_credentials",
        sa.Column("id", BigIntPK, primary_key=True),
        sa.Column("player_id", BigIntPK, nullable=False),
        sa.Column("season_id", BigIntPK, nullable=False),
        sa.Column("team_id", BigIntPK, nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], name="fk_player_qr_player", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], name="fk_player_qr_season", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_player_qr_team", ondelete="CASCADE"),
        sa.UniqueConstraint("player_id", "season_id", name="uq_player_qr_season"),
    )
    for column in ("id", "player_id", "season_id"):
        op.create_index("ix_player_qr_credentials_%s" % column, "player_qr_credentials", [column])

    op.create_table(
        "match_attendances",
        sa.Column("id", BigIntPK, primary_key=True),
        sa.Column("match_id", BigIntPK, nullable=False),
        sa.Column("player_id", BigIntPK, nullable=True),
        sa.Column("player_id_snapshot", BigIntPK, nullable=False),
        sa.Column("player_name_snapshot", sa.String(80), nullable=False),
        sa.Column("team_id", BigIntPK, nullable=False),
        sa.Column("team_name_snapshot", sa.String(80), nullable=False),
        sa.Column("shirt_number_snapshot", sa.Integer(), nullable=True),
        sa.Column("status", sa.Enum("PRESENT", "VOIDED", name="attendancestatus"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_by_id", BigIntPK, nullable=True),
        sa.Column("confirmed_by_name_snapshot", sa.String(80), nullable=False),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("voided_by_id", BigIntPK, nullable=True),
        sa.Column("void_reason", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], name="fk_attendance_match", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], name="fk_attendance_player", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_attendance_team"),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["users.id"], name="fk_attendance_confirmed_by", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["voided_by_id"], ["users.id"], name="fk_attendance_voided_by", ondelete="SET NULL"),
        sa.UniqueConstraint("match_id", "player_id_snapshot", name="uq_match_attendance_player"),
    )
    for column in ("id", "match_id", "player_id", "team_id", "status"):
        op.create_index("ix_match_attendances_%s" % column, "match_attendances", [column])


def downgrade():
    op.drop_table("match_attendances")
    op.drop_table("player_qr_credentials")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE attendancestatus")
        # A rollback must never grant a volunteer editing rights.
        op.execute("UPDATE users SET is_active = false, role = 'OPERATOR' WHERE role = 'VOLUNTEER'")
        op.execute("ALTER TYPE platformroles RENAME TO platformroles_with_volunteers")
        op.execute("CREATE TYPE platformroles AS ENUM ('OPERATOR', 'ADMIN', 'SUPER_ADMIN')")
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE platformroles USING role::text::platformroles")
        op.execute("DROP TYPE platformroles_with_volunteers")
    else:
        op.execute("UPDATE users SET is_active = false, role = 'OPERATOR' WHERE role = 'VOLUNTEER'")
