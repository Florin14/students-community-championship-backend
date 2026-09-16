"""The websocket lifecycle shared by both endpoints.

Origin is checked by hand because CORSMiddleware does not see websocket
handshakes. A close code can only travel after the handshake, so a refused
origin is accepted and closed with 4403 - the browser gets a code it can
decide not to retry on, rather than an anonymous handshake failure.
"""
import asyncio
import logging
import os
from typing import Awaitable, Callable, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

from .hub import hub

logger = logging.getLogger(__name__)

CLOSE_FORBIDDEN_ORIGIN = 4403
PING_SECONDS = 25.0


def allowed_origins() -> List[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "*")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def origin_allowed(origin: Optional[str], allowed: List[str]) -> bool:
    """Exact-match origin check.

    Browsers always send Origin on a websocket handshake, so a request without
    one comes from a non-browser client (curl, a smoke test) and CORS-style
    protection does not apply. `*` allows everything.
    """
    if not origin:
        return True
    if "*" in allowed:
        return True
    return origin.rstrip("/") in allowed


async def _pinger(websocket: WebSocket) -> None:
    """Keeps proxies from idling the connection out between two goals."""
    while True:
        await asyncio.sleep(PING_SECONDS)
        await websocket.send_json({"type": "ping"})


async def serve_socket(
    websocket: WebSocket, join: Callable[[WebSocket], Awaitable[bool]]
) -> None:
    if not origin_allowed(websocket.headers.get("origin"), allowed_origins()):
        await websocket.accept()
        await websocket.close(code=CLOSE_FORBIDDEN_ORIGIN)
        return
    await websocket.accept()
    if not await join(websocket):
        return
    ping_task = asyncio.get_event_loop().create_task(_pinger(websocket))
    try:
        while True:
            # Clients have nothing to say; a "pong" or anything else is ignored.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as error:  # noqa: BLE001 - a socket ending is not an error
        logger.debug("socket ended: %s", error)
    finally:
        ping_task.cancel()
        hub.leave(websocket)
