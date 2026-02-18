from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import config
from core.models import Peer, new_peer_id
from core.state import (
    PEERS,
    ROOMS,
    STATE_LOCK,
    broadcast_room,
    remove_peer,
    send_to_peer,
    validate_message,
    ws_send,
)

router = APIRouter()


logger = logging.getLogger(__name__)


async def heartbeat_loop(peer_id: str) -> None:
    """Periodically ping the client and timeout idle connections."""

    while True:
        await asyncio.sleep(config.PING_INTERVAL_SEC)

        async with STATE_LOCK:
            peer = PEERS.get(peer_id)
            if not peer:
                return
            ws = peer.ws
            last_seen = peer.last_seen

        if time.time() - last_seen > config.PING_TIMEOUT_SEC:
            logger.info("peer timeout peer_id=%s", peer_id)
            try:
                await ws.close(code=1001)
            except Exception:
                pass
            async with STATE_LOCK:
                await remove_peer(peer_id, reason="timeout")
            return

        try:
            await ws_send(ws, {"type": "ping", "ts": int(time.time())})
        except Exception:
            logger.info("peer ping send failed peer_id=%s", peer_id)
            async with STATE_LOCK:
                await remove_peer(peer_id, reason="send-failed")
            return


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    logger.info("ws connected client=%s", getattr(ws, "client", None))

    peer_id = new_peer_id()
    peer = Peer(peer_id=peer_id, ws=ws)

    async with STATE_LOCK:
        PEERS[peer_id] = peer

    logger.info("ws assigned peer_id=%s", peer_id)

    await ws_send(ws, {"type": "welcome", "peer_id": peer_id})

    hb_task = asyncio.create_task(heartbeat_loop(peer_id))

    try:
        while True:
            raw = await ws.receive_text()
            now = time.time()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("ws invalid json peer_id=%s", peer_id)
                await ws_send(ws, {"type": "error", "error": "invalid-json"})
                continue

            err = validate_message(msg)
            if err:
                logger.warning("ws invalid message peer_id=%s error=%s", peer_id, err)
                await ws_send(ws, {"type": "error", "error": err})
                continue

            async with STATE_LOCK:
                if peer_id in PEERS:
                    PEERS[peer_id].last_seen = now

            mtype = msg["type"]

            if mtype not in ("ping", "pong"):
                logger.debug("ws recv peer_id=%s type=%s", peer_id, mtype)

            if mtype == "pong":
                continue

            if mtype == "join":
                room = str(msg.get("room", "")).strip()
                name = str(msg.get("name", "")).strip()
                if not room:
                    await ws_send(ws, {"type": "error", "error": "join requires room"})
                    continue

                async with STATE_LOCK:
                    p = PEERS.get(peer_id)
                    if not p:
                        break

                    if p.room and p.room != room:
                        old_room = p.room
                        if old_room in ROOMS and peer_id in ROOMS[old_room]:
                            ROOMS[old_room].remove(peer_id)
                            if not ROOMS[old_room]:
                                ROOMS.pop(old_room, None)
                        await broadcast_room(
                            old_room,
                            {"type": "peer-left", "peer_id": peer_id, "reason": "switched-room"},
                            exclude=peer_id,
                        )

                    p.room = room
                    p.name = name

                    ROOMS.setdefault(room, set()).add(peer_id)

                    logger.info(
                        "peer joined peer_id=%s room=%s name_set=%s members=%s",
                        peer_id,
                        room,
                        bool(name),
                        len(ROOMS.get(room, set())),
                    )

                    roster = []
                    for pid in ROOMS.get(room, set()):
                        if pid == peer_id:
                            continue
                        other = PEERS.get(pid)
                        if other:
                            roster.append({"peer_id": pid, "name": other.name})

                await ws_send(ws, {"type": "joined", "room": room, "peers": roster})

                await broadcast_room(
                    room,
                    {"type": "peer-joined", "peer": {"peer_id": peer_id, "name": name}},
                    exclude=peer_id,
                )
                continue

            if mtype == "leave":
                async with STATE_LOCK:
                    p = PEERS.get(peer_id)
                    if not p:
                        break
                    room = p.room
                    p.room = ""
                    if room and room in ROOMS and peer_id in ROOMS[room]:
                        ROOMS[room].remove(peer_id)
                        if not ROOMS[room]:
                            ROOMS.pop(room, None)

                if room:
                    logger.info("peer left peer_id=%s room=%s", peer_id, room)
                    await ws_send(ws, {"type": "left", "room": room})
                    await broadcast_room(
                        room,
                        {"type": "peer-left", "peer_id": peer_id, "reason": "left"},
                        exclude=peer_id,
                    )
                continue

            # Relay messages peer-to-peer
            if "to" in msg:
                to_peer = str(msg.get("to", "")).strip()
                if not to_peer:
                    await ws_send(ws, {"type": "error", "error": 'invalid "to"'})
                    continue

                relay = dict(msg)
                relay["from"] = peer_id

                if mtype in ("offer", "answer"):
                    sdp = str(msg.get("sdp", ""))
                    logger.info("relay %s from=%s to=%s sdp_len=%s", mtype, peer_id, to_peer, len(sdp))
                elif mtype == "ice":
                    logger.debug("relay ice from=%s to=%s", peer_id, to_peer)
                else:
                    logger.debug("relay type=%s from=%s to=%s", mtype, peer_id, to_peer)

                ok = await send_to_peer(to_peer, relay)
                if not ok:
                    logger.info("relay failed from=%s to=%s type=%s", peer_id, to_peer, mtype)
                    await ws_send(ws, {"type": "error", "error": "peer-not-found", "to": to_peer})
                continue

            # Broadcast to room
            if mtype == "broadcast":
                async with STATE_LOCK:
                    p = PEERS.get(peer_id)
                    room = p.room if p else ""
                if not room:
                    await ws_send(ws, {"type": "error", "error": "not-in-room"})
                    continue

                async with STATE_LOCK:
                    recipients = len(ROOMS.get(room, set()))

                logger.info("broadcast from=%s room=%s recipients=%s", peer_id, room, recipients)

                relay = dict(msg)
                relay["from"] = peer_id
                await broadcast_room(room, relay, exclude=None)
                continue

            await ws_send(ws, {"type": "error", "error": f"unknown type: {mtype}"})

    except WebSocketDisconnect:

        logger.info("ws disconnect peer_id=%s", peer_id)
        pass
    except Exception:

        logger.exception("ws endpoint error peer_id=%s", peer_id)
    finally:
        hb_task.cancel()
        async with STATE_LOCK:
            await remove_peer(peer_id, reason="disconnect")
        logger.info("ws cleaned up peer_id=%s", peer_id)
        try:
            await ws.close()
        except Exception:
            pass
