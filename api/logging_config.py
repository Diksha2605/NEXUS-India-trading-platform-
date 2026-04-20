# ============================================================
#  NXIO — api/logging_config.py
#  Structured JSON Logging + Request ID Middleware
# ============================================================
import logging
import json
import uuid
import time
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


# ── JSON Log Formatter ────────────────────────────────────
class JSONFormatter(logging.Formatter):
    """Formats every log line as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        # Attach extra fields if present (e.g. request_id)
        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            if hasattr(record, key):
                log_obj[key] = getattr(record, key)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


# ── Setup Root Logger ─────────────────────────────────────
def setup_logging(log_level: str = "INFO") -> None:
    """Call once at startup to configure JSON logging."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "uvicorn.error", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ── Request ID Middleware ─────────────────────────────────
class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Attaches a unique X-Request-ID to every request/response.
    Logs method, path, status code, and duration for every call.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]   # short 8-char ID
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        response.headers["X-Request-ID"] = request_id

        logger = logging.getLogger("nxio.access")
        logger.info(
            f"{request.method} {request.url.path} {response.status_code}",
            extra={
                "request_id":  request_id,
                "method":      request.method,
                "path":        str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response