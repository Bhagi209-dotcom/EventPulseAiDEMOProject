"""Room-scoped WebSocket connection manager."""
from typing import Dict, List
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, code: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.rooms.setdefault(code, []).append(websocket)

    def disconnect(self, code: str, websocket: WebSocket) -> None:
        if code in self.rooms and websocket in self.rooms[code]:
            self.rooms[code].remove(websocket)
            if not self.rooms[code]:
                del self.rooms[code]

    async def broadcast(self, code: str, payload: dict) -> None:
        conns = list(self.rooms.get(code, []))
        stale: List[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(code, ws)


ws_manager = ConnectionManager()
