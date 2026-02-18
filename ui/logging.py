from __future__ import annotations

import logging

from PySide6 import QtCore


class LogBridge(QtCore.QObject):
    log = QtCore.Signal(str)


class QtSignalLogHandler(logging.Handler):
    def __init__(self, bridge: LogBridge):
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()

        # Emitting from non-UI threads is OK; Qt will queue delivery.
        try:
            self._bridge.log.emit(msg)
        except Exception:
            # Never let logging crash the app.
            pass


class DisplayNameFormatter(logging.Formatter):
    def __init__(self, fmt: str):
        super().__init__(fmt=fmt)
        self._name_map = {
            # Uvicorn uses this logger for lifecycle + protocol logs; it's not
            # actually an error level.
            "uvicorn.error": "uvicorn",
        }

    def format(self, record: logging.LogRecord) -> str:
        original_name = record.name
        mapped = self._name_map.get(original_name)
        if mapped:
            record.name = mapped
        try:
            return super().format(record)
        finally:
            record.name = original_name


def install_qt_log_handler(bridge: LogBridge, level: str | int | None = None) -> QtSignalLogHandler:
    root = logging.getLogger()

    # If we already installed one (e.g. hot-reload / repeated startup), reuse it.
    for existing in list(root.handlers):
        if isinstance(existing, QtSignalLogHandler):
            return existing

    handler = QtSignalLogHandler(bridge)
    handler.setFormatter(DisplayNameFormatter(fmt="%(asctime)s %(levelname)s %(name)s: %(message)s"))

    if level is not None:
        handler.setLevel(level)

    root.addHandler(handler)

    # Uvicorn logs via `uvicorn.*` loggers. We rely on propagation to the root
    # handler (installed above) to avoid duplicate entries.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.propagate = True
        # If a previous run attached Qt handlers directly, remove them.
        for h in list(lg.handlers):
            if isinstance(h, QtSignalLogHandler):
                lg.removeHandler(h)

    return handler
