"""In-memory registry of authenticated device WebSocket connections.

A device is only registered here after successful challenge-response
authentication, so `is_connected()` reflects a real authenticated
connection - never mere existence in the database.

Thread-safe via an asyncio lock; FastAPI WebSocket endpoints run on the
event loop, so async methods are used for sends.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, Any] = {}  # device_id -> WebSocket
        self._lock = asyncio.Lock()

    async def register(self, device_id: int, websocket: Any) -> None:
        async with self._lock:
            self._connections[device_id] = websocket
        logger.info("device %s connected (ws registered)", device_id)

    async def unregister(self, device_id: int, websocket: Any | None = None) -> None:
        async with self._lock:
            current = self._connections.get(device_id)
            if websocket is None or current is websocket:
                self._connections.pop(device_id, None)
        logger.info("device %s disconnected (ws unregistered)", device_id)

    def is_connected(self, device_id: int) -> bool:
        return device_id in self._connections

    def connected_ids(self) -> list[int]:
        return list(self._connections.keys())

    async def send_to_device(self, device_id: int, payload: dict) -> bool:
        """Send a JSON message to a device. Returns True when delivered."""
        websocket = self._connections.get(device_id)
        if websocket is None:
            return False
        try:
            await websocket.send_json(payload)
            return True
        except Exception as exc:  # noqa: BLE001 - connection may be dead
            logger.warning("ws send to device %s failed: %s", device_id, exc)
            await self.unregister(device_id, websocket)
            return False

    async def broadcast(self, payload: dict) -> None:
        for device_id in list(self._connections.keys()):
            await self.send_to_device(device_id, payload)


connection_manager = ConnectionManager()
