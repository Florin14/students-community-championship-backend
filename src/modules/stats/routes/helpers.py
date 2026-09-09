from typing import Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from modules.player.models import PlayerModel
from modules.player.services import get_player_stats_map
from modules.stats.models import TopPlayerItem


def build_top_players(
    db: Session,
    season_id: Optional[int],
    sort_key,
    limit: int,
    keep=lambda s: True,
) -> List[TopPlayerItem]:
    """Rank players by the given key over their per-season stats."""
    stats: Dict[int, Dict[str, int]] = get_player_stats_map(
        db, season_id=season_id
    )
    ranked = sorted(
        (item for item in stats.items() if keep(item[1])),
        key=lambda item: sort_key(item[1]),
        reverse=True,
    )[:limit]

    if not ranked:
        return []

    players = {
        player.id: player
        for player in db.query(PlayerModel)
        .options(joinedload(PlayerModel.team))
        .filter(PlayerModel.id.in_([player_id for player_id, _ in ranked]))
        .all()
    }

    items = []
    for player_id, player_stats in ranked:
        player = players.get(player_id)
        if player is None:
            continue
        items.append(
            TopPlayerItem(
                playerId=player.id,
                name=player.name,
                teamId=player.teamId,
                teamName=player.teamName,
                avatar=player.avatar,
                goals=player_stats["goals"],
                ownGoals=player_stats["ownGoals"],
                assists=player_stats["assists"],
                yellowCards=player_stats["yellowCards"],
                redCards=player_stats["redCards"],
            )
        )
    return items
