from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health():
    return JSONResponse({"ok": True, "ts": int(time.time())})
