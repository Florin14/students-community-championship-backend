"""Tell whoever is interested that a match changed.

The API is the only writer, so it is the one place that knows when a viewer
could see something new: a goal, a card, a kickoff, a final whistle. After the
commit the route calls `publish_match_changed()` and every registered listener
gets the notice - in production that is the websocket hub
(modules/live/services/hub.py) sitting in the same process, in the tests it is
a recorder.

The notice carries NO payload, only which match changed and why. Whoever
listens re-reads the match through the same code the HTTP routes use, so the
browsers always receive exactly what a poll would have returned and there is
one serializer to keep correct rather than two.

Publishing is best-effort and never fails the request: the row is already
committed and the frontend's polling fallback still picks it up.
"""
import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

MESSAGE_TYPE = "match.updated"


class LiveReason:
    """Why a match changed. Free text on the wire, fixed values in code so the
    hub (and the tests) can rely on them."""

    MATCH_CREATED = "match.created"
    MATCH_UPDATED = "match.updated"
    MATCH_DELETED = "match.deleted"
    MATCH_STARTED = "match.started"
    MATCH_PAUSED = "match.paused"
    MATCH_RESUMED = "match.resumed"
    MATCH_FINISHED = "match.finished"
    MATCH_REOPENED = "match.reopened"
    EVENT_ADDED = "event.added"
    EVENT_VOIDED = "event.voided"
    EVENT_UNDONE = "event.undone"


Listener = Callable[[Dict[str, Any]], None]

_lock = threading.Lock()
_listeners = []  # type: List[Listener]


def subscribe_live(listener: Listener) -> None:
    with _lock:
        if listener not in _listeners:
            _listeners.append(listener)


def unsubscribe_live(listener: Listener) -> None:
    with _lock:
        if listener in _listeners:
            _listeners.remove(listener)


def publish_match_changed(
    matchId: int,
    seasonId: Optional[int],
    reason: str,
    state: Optional[Any] = None,
) -> Dict[str, Any]:
    """Announce a change to every listener. Returns the notice that went out;
    a listener raising is logged and never reaches the caller."""
    message = {
        "type": MESSAGE_TYPE,
        "matchId": int(matchId),
        "seasonId": int(seasonId) if seasonId is not None else None,
        "state": getattr(state, "value", state),
        "reason": reason,
        "at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }
    with _lock:
        listeners = list(_listeners)
    for listener in listeners:
        try:
            listener(message)
        except Exception as exc:  # noqa: BLE001 - never fail the request
            logger.warning(
                "Live listener failed for match %s (%s): %s",
                matchId,
                reason,
                exc,
            )
    return message
