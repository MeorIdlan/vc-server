from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

from fastapi import WebSocket


def new_peer_id() -> str:
    """Short URL-safe id."""

    return secrets.token_urlsafe(8)


@dataclass
class Peer:
    peer_id: str
    ws: WebSocket
    name: str = ""
    room: str = ""
    last_seen: float = field(default_factory=lambda: time.time())
