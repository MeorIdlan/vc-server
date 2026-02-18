from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

from core.models import Peer


logger = logging.getLogger(__name__)


# peer_id -> Peer
PEERS: Dict[str, Peer] = {}

# room_id -> set(peer_id)
ROOMS: Dict[str, Set[str]] = {}

# async lock for shared state
STATE_LOCK = asyncio.Lock()


async def ws_send(ws: WebSocket, payload: Dict[str, Any]) -> None:
    await ws.send_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))


async def send_to_peer(peer_id: str, payload: Dict[str, Any]) -> bool:
    peer = PEERS.get(peer_id)
    if not peer:
        logger.debug("send_to_peer peer not found peer_id=%s", peer_id)
        return False
    try:
        await ws_send(peer.ws, payload)
        return True
    except Exception:
        logger.info("send_to_peer failed peer_id=%s", peer_id)
        return False


async def broadcast_room(room: str, payload: Dict[str, Any], exclude: Optional[str] = None) -> None:
    peer_ids = ROOMS.get(room, set()).copy()
    logger.debug("broadcast_room room=%s recipients=%s", room, len(peer_ids))
    for pid in peer_ids:
        if exclude and pid == exclude:
            continue
        await send_to_peer(pid, payload)


async def remove_peer(peer_id: str, reason: str = "disconnect") -> None:
    """Remove peer from server state and notify room.

    Must be called under STATE_LOCK.
    """

    peer = PEERS.pop(peer_id, None)
    if not peer:
        return

    logger.info("remove_peer peer_id=%s reason=%s room=%s", peer_id, reason, peer.room)

    room = peer.room
    if room:
        members = ROOMS.get(room)
        if members and peer_id in members:
            members.remove(peer_id)
            if not members:
                ROOMS.pop(room, None)

        await broadcast_room(
            room,
            {"type": "peer-left", "peer_id": peer_id, "reason": reason},
            exclude=peer_id,
        )


def validate_message(msg: Any) -> Optional[str]:
    if not isinstance(msg, dict):
        return "message must be a JSON object"
    if "type" not in msg or not isinstance(msg["type"], str):
        return 'missing/invalid "type"'
    return None
