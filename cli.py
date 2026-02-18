from __future__ import annotations

import argparse

import uvicorn
from fastapi import FastAPI

from .logging_config import setup_logging


def run(app: FastAPI) -> None:
    parser = argparse.ArgumentParser(description="Tiny WebRTC signaling server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--log-level",
        default=None,
        help="Logging level (debug, info, warning, error). Can also use VC_SERVER_LOG_LEVEL or VC_LOG_LEVEL.",
    )
    args = parser.parse_args()

    setup_logging(args.log_level)
    uvicorn.run(app, host=args.host, port=args.port, log_level=(args.log_level or "info"))
