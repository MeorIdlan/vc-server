"""Tiny WebRTC signaling server.

Public entrypoint for uvicorn: `server.app:app`.
"""

from __future__ import annotations

from fastapi import FastAPI

from .api.http import router as http_router
from .api.ws import router as ws_router


def create_app() -> FastAPI:
    app = FastAPI(title="Tiny Signaling Server")
    app.include_router(http_router)
    app.include_router(ws_router)
    return app


app = create_app()


def main() -> None:
    from .cli import run

    run(app)


if __name__ == "__main__":
    main()