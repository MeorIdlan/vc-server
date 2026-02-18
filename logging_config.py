from __future__ import annotations

import logging
import os
from typing import Optional


def setup_logging(level: Optional[str] = None) -> None:
    """Configure stdlib logging for the server.

    Uvicorn often configures logging itself; in that case we avoid overriding
    handlers and only ensure the root logger has a sensible level.
    """

    effective_level = (level or os.environ.get("VC_SERVER_LOG_LEVEL") or os.environ.get("VC_LOG_LEVEL") or "INFO").upper()

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=effective_level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    else:
        root.setLevel(effective_level)
