# vc-server

This repo contains the **signaling server** used by `vc-client`.

- HTTP API: FastAPI
- WebSocket signaling: FastAPI WebSocket endpoint
- Runtime: Uvicorn
- Optional UI: PySide6 log window that runs the server in a background thread

The server’s job is to help peers:
- join/leave “rooms”
- learn the current roster
- exchange WebRTC negotiation messages (`offer`/`answer`/`ice`)

It does **not** forward audio/video media; media is peer-to-peer.

## Endpoints

- `GET /health`
  - Returns `{ "ok": true, "ts": <unix> }`
  - Implemented in [api/http.py](api/http.py)

- `WS /ws`
  - JSON message protocol for joining rooms + relaying peer messages
  - Implemented in [api/ws.py](api/ws.py)

Server app assembly:
- [app.py](app.py)

## Server state model

State is held in-memory in a single process:
- `PEERS`: peer_id → WebSocket + metadata
- `ROOMS`: room_id → set(peer_id)

See [core/state.py](core/state.py) and [core/models.py](core/models.py).

Because state is in-memory:
- restarting the server drops all rooms
- horizontal scaling would require shared state (not implemented)

## Message behavior (summary)

On connect:
- server assigns a random `peer_id`
- sends `{ "type": "welcome", "peer_id": "..." }`

Join a room:
- client sends `{ "type": "join", "room": "...", "name": "..." }`
- server responds `{ "type": "joined", "room": "...", "peers": [...] }`
- server broadcasts `peer-joined` to the room

Relay:
- if a message includes `"to": "<peer_id>"`, the server forwards it to that peer and adds `"from": "<sender_peer_id>"`

Heartbeat:
- server periodically sends `ping`
- disconnects idle peers after a timeout

Tuning constants:
- [config.py](config.py)

## Install

```bash
pip install -r requirements.txt
```

GUI entry point: [gui.py](gui.py)
Qt log bridge: [ui/logging.py](ui/logging.py)

## Logging configuration

- CLI/GUI flag: `--log-level` (debug/info/warning/error)
- Environment variables:
  - `VC_SERVER_LOG_LEVEL` or `VC_LOG_LEVEL`

See [logging_config.py](logging_config.py).

## Downloading a Windows .exe (GitHub Releases)

If you don’t want to run from source, you can download a prebuilt Windows executable from the project’s GitHub Releases.

1. Open the repository on GitHub and go to **Releases**.
2. Open the latest release.
3. Under **Assets**, download `vc-server-windows.zip`.
4. Extract the zip and run `vc-server.exe`.

Notes:
- This executable starts the server in **GUI mode** (a log window) and listens on the host/port shown in the UI/logs.
- Windows may show SmartScreen for unsigned executables.

## Building the Windows .exe yourself

If you want to produce the executable locally (Windows), you can build it with PyInstaller.

Because the code uses package-relative imports (e.g. `from .ui.app import ...`), run PyInstaller from a directory where the `server` package is importable.

One simple approach on Windows is to open PowerShell in the **parent directory** that contains the repo folder (checked out as `server`). This builds the GUI entrypoint.

```powershell
python -m pip install --upgrade pip
python -m pip install -r server\requirements.txt

@'
from server.gui import main
raise SystemExit(main())
'@ | Set-Content -Encoding UTF8 build_entry.py

python -m PyInstaller --noconfirm --clean --onefile --windowed --name vc-server build_entry.py
```

Output:
- The executable will be at `dist\vc-server.exe`.
