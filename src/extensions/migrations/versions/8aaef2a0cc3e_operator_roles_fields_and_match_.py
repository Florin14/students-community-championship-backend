"""operator roles, fields and match assignment

Adds the three-role hierarchy from section 6 of the implementation plan, the
playing fields four matches run on in parallel, the operator-to-match
assignment table, and the match clock and result-lock columns.

Hand-adjusted after autogenerate:
- `elapsed_seconds` and `is_active` get server defaults, so the NOT NULL holds
  for rows that already exist.
- The role change is a Postgres enum value addition, not a type swap; on SQLite
  the enum is a plain VARCHAR and needs nothing.
- Foreign keys and constraints are named, so `downgrade()` can drop them.

Revision ID: 8aaef2a0cc3e
Revises: bad1afa4c31d
Create Date: 2026-09-09 16:57:22.832547

"""
from alembic import op
import sqlalchemy as sa

revision = '8aaef2a0cc3e'
down_revision = 'bad1afa4c31d'
branch_labels = None
depends_on = None

BigIntPK = sa.BigInteger().with_variant(sa.Integer(), 'sqlite')

NEW_ROLES = ('OPERATOR', 'SUPER_ADMIN')


def upgrade() -> None:
    bind = op.get_bind()
    isPostgres = bind.dialect.name == 'postgresql'

    op.create_table(
        'fields',
        sa.Column('id', BigIntPK, nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('short_name', sa.String(length=12), nullable=True),
        sa.Column('location', sa.String(length=160), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='pk_fields'),
        sa.UniqueConstraint('name', name='uq_fields_name'),
    )
    op.create_index(op.f('ix_fields_id'), 'fields', ['id'], unique=False)

    op.create_table(
        'match_operators',
        sa.Column('id', BigIntPK, nullable=False),
        sa.Column('match_id', BigIntPK, nullable=False),
        sa.Column('user_id', BigIntPK, nullable=False),
        sa.Column(
            'assigned_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['match_id'],
            ['matches.id'],
            name='fk_match_operators_match_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name='fk_match_operators_user_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_match_operators'),
        sa.UniqueConstraint('match_id', 'user_id', name='uq_match_operator'),
    )
    op.create_index(
        op.f('ix_match_operators_id'), 'match_operators', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_match_operators_match_id'),
        'match_operators',
        ['match_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_match_operators_user_id'),
        'match_operators',
        ['user_id'],
        unique=False,
    )

    # --- matches: field, clock and result lock -------------------------------
    op.add_column('matches', sa.Column('field_id', BigIntPK, nullable=True))
    op.add_column('matches', sa.Column('started_at', sa.DateTime(), nullable=True))
    op.add_column(
        'matches', sa.Column('running_since', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'matches',
        sa.Column(
            'elapsed_seconds',
            sa.Integer(),
            server_default='0',
            nullable=False,
        ),
    )
    op.add_column('matches', sa.Column('locked_at', sa.DateTime(), nullable=True))
    op.add_column(
        'matches', sa.Column('confirmed_at', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'matches', sa.Column('confirmed_by_id', BigIntPK, nullable=True)
    )
    op.create_index(
        op.f('ix_matches_field_id'), 'matches', ['field_id'], unique=False
    )

    with op.batch_alter_table('matches') as batch:
        batch.create_foreign_key(
            'fk_matches_field_id',
            'fields',
            ['field_id'],
            ['id'],
            ondelete='SET NULL',
        )
        batch.create_foreign_key(
            'fk_matches_confirmed_by_id',
            'users',
            ['confirmed_by_id'],
            ['id'],
            ondelete='SET NULL',
        )

    # Matches already played keep their result, and a result that exists is a
    # confirmed one, so lock them rather than leaving them open to overwrite.
    op.execute(
        """
        UPDATE matches
           SET locked_at = CURRENT_TIMESTAMP,
               confirmed_at = CURRENT_TIMESTAMP
         WHERE state = 'FINISHED'
           AND score_home IS NOT NULL
           AND score_away IS NOT NULL
        """
    )

    # --- users: active flag and the wider role enum --------------------------
    op.add_column(
        'users',
        sa.Column(
            'is_active',
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )

    if isPostgres:
        # The enum type already exists with a single value; widen it in place.
        # ALTER TYPE ... ADD VALUE is transactional from Postgres 12 onwards.
        for role in NEW_ROLES:
            op.execute(
                "ALTER TYPE platformroles ADD VALUE IF NOT EXISTS '%s'" % role
            )


def downgrade() -> None:
    bind = op.get_bind()
    isPostgres = bind.dialect.name == 'postgresql'

    if isPostgres:
        # Enum values cannot be dropped, so rebuild the type with ADMIN only.
        # Accounts on a removed role become plain admins; operators would
        # otherwise be left pointing at a value the type no longer holds.
        op.execute(
            "UPDATE users SET role = 'ADMIN' "
            "WHERE role IN ('OPERATOR', 'SUPER_ADMIN')"
        )
        op.execute("ALTER TYPE platformroles RENAME TO platformroles_old")
        op.execute("CREATE TYPE platformroles AS ENUM ('ADMIN')")
        op.execute(
            "ALTER TABLE users ALTER COLUMN role TYPE platformroles "
            "USING role::text::platformroles"
        )
        op.execute("DROP TYPE platformroles_old")

    # batch_alter_table rather than plain drop_column: SQLite gained DROP COLUMN
    # only in 3.35, and the local interpreter ships an older library.
    with op.batch_alter_table('users') as batch:
        batch.drop_column('is_active')

    op.drop_index(op.f('ix_matches_field_id'), table_name='matches')

    with op.batch_alter_table('matches') as batch:
        batch.drop_constraint('fk_matches_confirmed_by_id', type_='foreignkey')
        batch.drop_constraint('fk_matches_field_id', type_='foreignkey')
        batch.drop_column('confirmed_by_id')
        batch.drop_column('confirmed_at')
        batch.drop_column('locked_at')
        batch.drop_column('elapsed_seconds')
        batch.drop_column('running_since')
        batch.drop_column('started_at')
        batch.drop_column('field_id')

    op.drop_index(
        op.f('ix_match_operators_user_id'), table_name='match_operators'
    )
    op.drop_index(
        op.f('ix_match_operators_match_id'), table_name='match_operators'
    )
    op.drop_index(op.f('ix_match_operators_id'), table_name='match_operators')
    op.drop_table('match_operators')

    op.drop_index(op.f('ix_fields_id'), table_name='fields')
    op.drop_table('fields')
