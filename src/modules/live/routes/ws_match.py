from fastapi import WebSocket

from modules.live.services import hub, serve_socket

from .router import router


@router.websocket("/matches/{id}")
async def ws_match(websocket: WebSocket, id: int):
    """One match, pushed. A `match` frame on connect and on every change - the
    same body as `GET /matches/{id}`. Unknown id: `error` then close 4404."""
    await serve_socket(websocket, lambda ws: hub.join_match(ws, id))
