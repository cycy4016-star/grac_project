from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logger import get_logger

logger = get_logger("api")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start = datetime.now(timezone.utc)
        response = await call_next(request)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()

        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} "
            f"[{elapsed:.3f}s] req_id={request_id}"
        )

        response.headers["X-Request-ID"] = request_id
        return response


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLogMiddleware)
