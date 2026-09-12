"""match event log and audit log

Replaces the `goals` and `cards` tables with a single append-only event log,
and adds the audit trail.

The old tables recorded only what the final score was made of. Section 5 of the
implementation plan needs each action stored individually with its minute, its
author, the moment it was entered and a state of active / corrected / voided,
so a mistake can be cancelled rather than deleted. Existing goals and cards are
carried over as active events, so no match loses its history.

Hand-written after autogenerate: the data migration, the drop of the now unused
Postgres `cardtype` enum, and the removal of a spurious users.role type change
that autogenerate reports when comparing against SQLite.

Revision ID: a2be5663eafa
Revises: 8aaef2a0cc3e
Create Date: 2026-09-09 17:12:44.106221

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = 'a2be5663eafa'
down_revision = '8aaef2a0cc3e'
branch_labels = None
depends_on = None

BigIntPK = sa.BigInteger().with_variant(sa.Integer(), 'sqlite')

EVENT_TYPES = ('GOAL', 'OWN_GOAL', 'YELLOW_CARD', 'RED_CARD')
EVENT_STATUSES = ('ACTIVE', 'CORRECTED', 'VOIDED')
CARD_TYPES = ('YELLOW', 'RED')


def _event_type_enum():
    return sa.Enum(*EVENT_TYPES, name='matcheventtype')


def _event_status_enum():
    return sa.Enum(*EVENT_STATUSES, name='matcheventstatus')


def _events_insert_table():
    """A lightweight view of match_events for the data migration.

    Declared with the real enum types so the values are bound correctly on
    Postgres as well as SQLite.
    """
    return sa.Table(
        'match_events',
        sa.MetaData(),
        sa.Column('match_id', BigIntPK),
        sa.Column('client_event_id', sa.String(64)),
        sa.Column('type', _event_type_enum()),
        sa.Column('status', _event_status_enum()),
        sa.Column('team_id', BigIntPK),
        sa.Column('player_id', BigIntPK),
        sa.Column('player_name_snapshot', sa.String(80)),
        sa.Column('assist_player_id', BigIntPK),
        sa.Column('assist_name_snapshot', sa.String(80)),
        sa.Column('minute', sa.Integer),
        sa.Column('created_at', sa.DateTime),
    )


def upgrade() -> None:
    bind = op.get_bind()
    isPostgres = bind.dialect.name == 'postgresql'

    op.create_table(
        'match_events',
        sa.Column('id', BigIntPK, nullable=False),
        sa.Column('match_id', BigIntPK, nullable=False),
        sa.Column('client_event_id', sa.String(length=64), nullable=False),
        sa.Column('type', _event_type_enum(), nullable=False),
        sa.Column('status', _event_status_enum(), nullable=False),
        sa.Column('team_id', BigIntPK, nullable=False),
        sa.Column('player_id', BigIntPK, nullable=True),
        sa.Column('player_name_snapshot', sa.String(length=80), nullable=True),
        sa.Column('assist_player_id', BigIntPK, nullable=True),
        sa.Column('assist_name_snapshot', sa.String(length=80), nullable=True),
        sa.Column('minute', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_id', BigIntPK, nullable=True),
        sa.Column(
            'created_by_name_snapshot', sa.String(length=80), nullable=True
        ),
        sa.Column('voided_at', sa.DateTime(), nullable=True),
        sa.Column('voided_by_id', BigIntPK, nullable=True),
        sa.Column(
            'voided_by_name_snapshot', sa.String(length=80), nullable=True
        ),
        sa.Column('void_reason', sa.String(length=200), nullable=True),
        sa.Column('supersedes_event_id', BigIntPK, nullable=True),
        sa.ForeignKeyConstraint(
            ['match_id'],
            ['matches.id'],
            name='fk_match_events_match_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['team_id'], ['teams.id'], name='fk_match_events_team_id'
        ),
        sa.ForeignKeyConstraint(
            ['player_id'],
            ['players.id'],
            name='fk_match_events_player_id',
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['assist_player_id'],
            ['players.id'],
            name='fk_match_events_assist_player_id',
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['created_by_id'],
            ['users.id'],
            name='fk_match_events_created_by_id',
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['voided_by_id'],
            ['users.id'],
            name='fk_match_events_voided_by_id',
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['supersedes_event_id'],
            ['match_events.id'],
            name='fk_match_events_supersedes_event_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_match_events'),
        sa.UniqueConstraint(
            'match_id', 'client_event_id', name='uq_match_event_client_id'
        ),
    )
    for column in (
        'id',
        'match_id',
        'team_id',
        'player_id',
        'assist_player_id',
        'status',
        'type',
    ):
        op.create_index(
            op.f('ix_match_events_%s' % column),
            'match_events',
            [column],
            unique=False,
        )

    op.create_table(
        'audit_log',
        sa.Column('id', BigIntPK, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', BigIntPK, nullable=True),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('match_id', BigIntPK, nullable=True),
        sa.Column('user_id', BigIntPK, nullable=True),
        sa.Column('user_name_snapshot', sa.String(length=80), nullable=True),
        sa.Column('summary', sa.String(length=300), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ['match_id'],
            ['matches.id'],
            name='fk_audit_log_match_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name='fk_audit_log_user_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_audit_log'),
    )
    for column in (
        'id',
        'created_at',
        'entity_type',
        'entity_id',
        'action',
        'match_id',
    ):
        op.create_index(
            op.f('ix_audit_log_%s' % column),
            'audit_log',
            [column],
            unique=False,
        )

    _migrate_goals_and_cards_into_events(bind)

    op.drop_index('ix_goals_assist_player_id', table_name='goals')
    op.drop_index('ix_goals_id', table_name='goals')
    op.drop_index('ix_goals_match_id', table_name='goals')
    op.drop_index('ix_goals_scorer_id', table_name='goals')
    op.drop_table('goals')

    op.drop_index('ix_cards_id', table_name='cards')
    op.drop_index('ix_cards_match_id', table_name='cards')
    op.drop_index('ix_cards_player_id', table_name='cards')
    op.drop_table('cards')

    if isPostgres:
        # Nothing references the card type any more; the event type covers it.
        op.execute('DROP TYPE IF EXISTS cardtype')


def _migrate_goals_and_cards_into_events(bind) -> None:
    """Carry every existing goal and card over as an active event.

    Legacy rows get a deterministic client event id so re-running the import
    could never duplicate them, and a null author: nobody recorded who entered
    these before the event log existed, and inventing one would be worse than
    leaving it empty.
    """
    events = _events_insert_table()
    now = datetime.utcnow()
    rows = []

    goals = bind.execute(
        sa.text(
            "SELECT id, match_id, team_id, scorer_id, scorer_name_snapshot, "
            "assist_player_id, assist_name_snapshot, minute FROM goals"
        )
    ).mappings().all()
    for goal in goals:
        rows.append(
            {
                'match_id': goal['match_id'],
                'client_event_id': 'legacy-goal-%s' % goal['id'],
                'type': 'GOAL',
                'status': 'ACTIVE',
                'team_id': goal['team_id'],
                'player_id': goal['scorer_id'],
                'player_name_snapshot': goal['scorer_name_snapshot'],
                'assist_player_id': goal['assist_player_id'],
                'assist_name_snapshot': goal['assist_name_snapshot'],
                'minute': goal['minute'],
                'created_at': now,
            }
        )

    cards = bind.execute(
        sa.text(
            "SELECT id, match_id, team_id, player_id, player_name_snapshot, "
            "card_type, minute FROM cards"
        )
    ).mappings().all()
    for card in cards:
        rows.append(
            {
                'match_id': card['match_id'],
                'client_event_id': 'legacy-card-%s' % card['id'],
                'type': (
                    'YELLOW_CARD'
                    if str(card['card_type']).upper().endswith('YELLOW')
                    else 'RED_CARD'
                ),
                'status': 'ACTIVE',
                'team_id': card['team_id'],
                'player_id': card['player_id'],
                'player_name_snapshot': card['player_name_snapshot'],
                'assist_player_id': None,
                'assist_name_snapshot': None,
                'minute': card['minute'],
                'created_at': now,
            }
        )

    if rows:
        op.bulk_insert(events, rows)


def downgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        'goals',
        sa.Column('id', BigIntPK, nullable=False),
        sa.Column('match_id', BigIntPK, nullable=False),
        sa.Column('team_id', BigIntPK, nullable=False),
        sa.Column('scorer_id', BigIntPK, nullable=True),
        sa.Column('scorer_name_snapshot', sa.String(length=80), nullable=True),
        sa.Column('assist_player_id', BigIntPK, nullable=True),
        sa.Column('assist_name_snapshot', sa.String(length=80), nullable=True),
        sa.Column('minute', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['match_id'], ['matches.id'], name='fk_goals_match_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['team_id'], ['teams.id'], name='fk_goals_team_id'
        ),
        sa.ForeignKeyConstraint(
            ['scorer_id'], ['players.id'], name='fk_goals_scorer_id',
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['assist_player_id'], ['players.id'],
            name='fk_goals_assist_player_id', ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_goals'),
    )
    op.create_index('ix_goals_id', 'goals', ['id'], unique=False)
    op.create_index('ix_goals_match_id', 'goals', ['match_id'], unique=False)
    op.create_index('ix_goals_scorer_id', 'goals', ['scorer_id'], unique=False)
    op.create_index(
        'ix_goals_assist_player_id', 'goals', ['assist_player_id'], unique=False
    )

    op.create_table(
        'cards',
        sa.Column('id', BigIntPK, nullable=False),
        sa.Column('match_id', BigIntPK, nullable=False),
        sa.Column('team_id', BigIntPK, nullable=False),
        sa.Column('player_id', BigIntPK, nullable=True),
        sa.Column('player_name_snapshot', sa.String(length=80), nullable=True),
        sa.Column(
            'card_type', sa.Enum(*CARD_TYPES, name='cardtype'), nullable=False
        ),
        sa.Column('minute', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['match_id'], ['matches.id'], name='fk_cards_match_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['team_id'], ['teams.id'], name='fk_cards_team_id'
        ),
        sa.ForeignKeyConstraint(
            ['player_id'], ['players.id'], name='fk_cards_player_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_cards'),
    )
    op.create_index('ix_cards_id', 'cards', ['id'], unique=False)
    op.create_index('ix_cards_match_id', 'cards', ['match_id'], unique=False)
    op.create_index('ix_cards_player_id', 'cards', ['player_id'], unique=False)

    # Only active events map back; voided ones have no representation in the
    # old shape, which is precisely why the event log replaced it.
    op.execute(
        """
        INSERT INTO goals (
            match_id, team_id, scorer_id, scorer_name_snapshot,
            assist_player_id, assist_name_snapshot, minute
        )
        SELECT match_id, team_id, player_id, player_name_snapshot,
               assist_player_id, assist_name_snapshot, minute
          FROM match_events
         WHERE status = 'ACTIVE' AND type IN ('GOAL', 'OWN_GOAL')
        """
    )
    # Postgres will not assign a text CASE result to an enum column without a
    # cast; SQLite stores the enum as VARCHAR and has no cast to make.
    card_type_cast = '::cardtype' if bind.dialect.name == 'postgresql' else ''
    op.execute(
        """
        INSERT INTO cards (
            match_id, team_id, player_id, player_name_snapshot, card_type,
            minute
        )
        SELECT match_id, team_id, player_id, player_name_snapshot,
               (CASE WHEN type = 'YELLOW_CARD' THEN 'YELLOW' ELSE 'RED' END)%s,
               minute
          FROM match_events
         WHERE status = 'ACTIVE' AND type IN ('YELLOW_CARD', 'RED_CARD')
        """
        % card_type_cast
    )

    for column in (
        'id',
        'created_at',
        'entity_type',
        'entity_id',
        'action',
        'match_id',
    ):
        op.drop_index(op.f('ix_audit_log_%s' % column), table_name='audit_log')
    op.drop_table('audit_log')

    for column in (
        'id',
        'match_id',
        'team_id',
        'player_id',
        'assist_player_id',
        'status',
        'type',
    ):
        op.drop_index(
            op.f('ix_match_events_%s' % column), table_name='match_events'
        )
    op.drop_table('match_events')

    if bind.dialect.name == 'postgresql':
        op.execute('DROP TYPE IF EXISTS matcheventtype')
        op.execute('DROP TYPE IF EXISTS matcheventstatus')
