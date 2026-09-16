from typing import Optional

from fastapi import Query, WebSocket

from modules.live.services import hub, serve_socket

from .router import router


@router.websocket("/live")
async def ws_live(websocket: WebSocket, seasonId: Optional[int] = Query(None)):
    """The live feed, pushed. A `snapshot` frame on connect and another every
    time its `revision` changes - the same body as `GET /matches/live`."""
    await serve_socket(websocket, lambda ws: hub.join_live(ws, seasonId))
