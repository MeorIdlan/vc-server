from __future__ import annotations

import argparse
import logging
import sys
import threading
from typing import Optional

import uvicorn

from .app import app as fastapi_app
from .logging_config import setup_logging


logger = logging.getLogger(__name__)


class UvicornThread:
    def __init__(self, host: str, port: int, log_level: str) -> None:
        self._host = host
        self._port = port
        self._log_level = log_level

        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        config = uvicorn.Config(
            fastapi_app,
            host=self._host,
            port=self._port,
            log_level=self._log_level,
            # In GUI mode we want to capture logs via the stdlib logging handlers
            # we install (Qt handler). Uvicorn's default logging config can
            # replace handlers and prevent our UI from seeing its startup logs.
            log_config=None,
        )
        self._server = uvicorn.Server(config)

        def _run() -> None:
            assert self._server is not None
            self._server.run()

        self._thread = threading.Thread(target=_run, name="uvicorn-thread", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        if not self._server:
            return
        self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=timeout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tiny WebRTC signaling server (GUI)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--log-level",
        default=None,
        help="Logging level (debug, info, warning, error). Can also use VC_SERVER_LOG_LEVEL or VC_LOG_LEVEL.",
    )
    args = parser.parse_args(argv)

    setup_logging(args.log_level)
    effective_level = (args.log_level or "info").lower()

    try:
        from .ui.app import create_qt_app
        from .ui.logging import LogBridge, install_qt_log_handler
        from .ui.windows import LogWindow
    except Exception as e:
        print(f"Failed to import UI dependencies: {e}")
        print("Install server deps with: pip install -r server/requirements.txt")
        return 2

    qt_app = create_qt_app()

    bridge = LogBridge()
    handler = install_qt_log_handler(bridge)
    handler.setLevel(logging.DEBUG)

    # When uvicorn's `log_config` is disabled, it won't configure its own
    # logger levels. Ensure we don't accidentally suppress its startup INFO logs.
    level_map = {
        "critical": logging.CRITICAL,
        "error": logging.ERROR,
        "warning": logging.WARNING,
        "warn": logging.WARNING,
        "info": logging.INFO,
        "debug": logging.DEBUG,
        "trace": logging.DEBUG,
    }
    uvicorn_level = level_map.get(effective_level, logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(uvicorn_level)

    window = LogWindow()
    bridge.log.connect(window.append_log)

    server = UvicornThread(host=str(args.host), port=int(args.port), log_level=effective_level)
    server.start()

    logger.info("server ui started host=%s port=%s", args.host, args.port)
    window.show()

    def _shutdown() -> None:
        logger.info("server ui shutdown")
        server.stop()

    qt_app.aboutToQuit.connect(_shutdown)
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
