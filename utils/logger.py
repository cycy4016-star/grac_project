"""
Structured Logger

Replaces the ad-hoc ``logging.getLogger`` calls scattered across BaseAgent
with a single, consistent setup that:

- Emits JSON-structured log records to per-agent rotating files
- Mirrors every record to the console (plain text) for development
- Writes a combined ``grac.log`` for full-system tailing
- Exposes a clean ``get_logger(name)`` factory used everywhere

Usage:
    from utils.logger import get_logger

    logger = get_logger("IngestorAgent")
    logger.info("Extracting PDF", extra={"pdf_path": "act843.pdf", "sector": "data_protection"})
    logger.error("Extraction failed", extra={"error": str(e)})

JSON log record shape
---------------------
Every line in ``*.log`` files is a JSON object::

    {
        "timestamp": "2025-03-15T14:22:01.334Z",
        "level":     "INFO",
        "logger":    "IngestorAgent",
        "message":   "Extracting PDF",
        "pdf_path":  "act843.pdf",
        "sector":    "data_protection"
    }

Drop-in replacement for ``logging.getLogger``
---------------------------------------------
The returned logger is a standard ``logging.Logger``, so all existing
``self.logger.info/warning/error/debug`` calls in agents work unchanged.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

class _JSONFormatter(logging.Formatter):
    """
    Formats each log record as a single-line JSON object.

    ``extra`` kwargs passed to logger calls are merged into the top-level
    JSON object, making structured fields first-class rather than buried
    in a message string.
    """

    # Fields on LogRecord that belong to the logging internals — we strip
    # these before merging ``extra`` fields into the JSON output.
    _INTERNAL_FIELDS = frozenset({
        "args", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "message", "module", "msecs",
        "msg", "name", "pathname", "process", "processName", "relativeCreated",
        "stack_info", "taskName", "thread", "threadName",
    })

    def format(self, record: logging.LogRecord) -> str:
        # Resolve the message (applies % formatting if args were given)
        record.message = record.getMessage()

        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        payload: dict[str, Any] = {
            "timestamp": ts,
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.message,
        }

        # Merge any extra fields the caller passed
        for key, val in record.__dict__.items():
            if key not in self._INTERNAL_FIELDS and not key.startswith("_"):
                payload[key] = val

        # Attach exception info if present
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Plain-text console formatter (human-readable during development)
# ---------------------------------------------------------------------------

class _ConsoleFormatter(logging.Formatter):
    """Coloured console output for interactive development."""

    _COLOURS = {
        logging.DEBUG:    "\033[36m",   # cyan
        logging.INFO:     "\033[32m",   # green
        logging.WARNING:  "\033[33m",   # yellow
        logging.ERROR:    "\033[31m",   # red
        logging.CRITICAL: "\033[35m",   # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelno, "")
        reset  = self._RESET if colour else ""
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        return (
            f"{colour}[{ts}] {record.levelname:<8}{reset} "
            f"{record.name}: {record.getMessage()}"
        )


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

# Track which loggers we've already configured so we never double-add handlers
_configured: set[str] = set()

# Resolved at first call and cached
_logs_dir: Optional[Path] = None


def _get_logs_dir() -> Path:
    global _logs_dir
    if _logs_dir is None:
        try:
            from config.settings import settings
            _logs_dir = Path(settings.LOGS_DIR)
        except Exception:
            # Fallback if settings isn't available (e.g. during testing)
            _logs_dir = Path(__file__).parent.parent / "data" / "logs"
        _logs_dir.mkdir(parents=True, exist_ok=True)
    return _logs_dir


def _resolve_level() -> int:
    """Read LOG_LEVEL from settings or env, defaulting to INFO."""
    try:
        from config.settings import settings
        level_str = settings.LOG_LEVEL
    except Exception:
        level_str = os.getenv("LOG_LEVEL", "INFO")
    return getattr(logging, level_str.upper(), logging.INFO)


def get_logger(
    name: str,
    *,
    console: bool = True,
    level: Optional[int] = None,
    max_bytes: int = 5 * 1024 * 1024,   # 5 MB per file
    backup_count: int = 3,
) -> logging.Logger:
    """
    Return a configured logger for *name*.

    Calling this multiple times with the same *name* is safe — handlers are
    added only once.

    Args:
        name: Logger name, typically the agent class name
              (e.g. ``"IngestorAgent"``).
        console: Whether to attach a human-readable stderr handler.
                 Defaults to True.  Set False in production/testing to
                 suppress console noise.
        level: Override the log level.  Defaults to ``settings.LOG_LEVEL``.
        max_bytes: Max size of each rotating log file (default 5 MB).
        backup_count: Number of rotated backups to keep (default 3).

    Returns:
        A ``logging.Logger`` ready to use.
    """
    logger = logging.getLogger(name)

    if name in _configured:
        return logger

    _configured.add(name)
    resolved_level = level if level is not None else _resolve_level()
    logger.setLevel(resolved_level)
    logger.propagate = False  # prevent double-logging via root logger

    logs_dir = _get_logs_dir()
    json_fmt  = _JSONFormatter()
    plain_fmt = _ConsoleFormatter()

    # ---- Per-agent rotating file handler (JSON) -------------------------
    agent_log = logs_dir / f"{name.lower()}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        agent_log,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(json_fmt)
    file_handler.setLevel(resolved_level)
    logger.addHandler(file_handler)

    # ---- Combined system log (JSON, all agents) -------------------------
    combined_log = logs_dir / "grac.log"
    combined_handler = logging.handlers.RotatingFileHandler(
        combined_log,
        maxBytes=max_bytes * 2,   # Combined log can be larger
        backupCount=backup_count,
        encoding="utf-8",
    )
    combined_handler.setFormatter(json_fmt)
    combined_handler.setLevel(resolved_level)
    logger.addHandler(combined_handler)

    # ---- Console handler (plain text, INFO+ only) -----------------------
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(plain_fmt)
        console_handler.setLevel(max(resolved_level, logging.INFO))
        logger.addHandler(console_handler)

    return logger


# ---------------------------------------------------------------------------
# Convenience: execution event logger
# ---------------------------------------------------------------------------

def log_execution_event(
    agent_name: str,
    event: str,
    sector: str,
    *,
    status: str = "info",
    duration_seconds: Optional[float] = None,
    extra: Optional[dict] = None,
) -> None:
    """
    Write a structured execution event to the combined ``execution.jsonl`` log.

    This is a thin wrapper around ``file_handler.append_jsonl`` — kept here
    so logging concerns stay in one module.

    Args:
        agent_name: Name of the agent emitting the event.
        event: Short description, e.g. ``"extraction_started"``.
        sector: Active sector ID.
        status: ``"info"`` | ``"success"`` | ``"warning"`` | ``"error"``.
        duration_seconds: Optional wall-clock duration of the operation.
        extra: Any additional key/value pairs to include in the record.
    """
    from utils.file_handler import file_handler as fh

    record: dict[str, Any] = {
        "timestamp":  datetime.now(tz=timezone.utc).isoformat(),
        "agent":      agent_name,
        "event":      event,
        "sector":     sector,
        "status":     status,
    }
    if duration_seconds is not None:
        record["duration_seconds"] = round(duration_seconds, 3)
    if extra:
        record.update(extra)

    logs_dir = _get_logs_dir()
    fh.append_jsonl(logs_dir / "execution.jsonl", record)


# ---------------------------------------------------------------------------
# Patch BaseAgent to use the new logger  (optional, non-breaking)
# ---------------------------------------------------------------------------

def patch_base_agent() -> None:
    """
    Monkey-patch ``BaseAgent._setup_logger`` to use ``get_logger``.

    Call this once at application startup (e.g. in ``main.py``) to upgrade
    all agent loggers to structured JSON without touching the agent files.

    Agents that have already been instantiated before this call will keep
    their old loggers; only new instances pick up the patch.
    """
    try:
        from agents.base_agent import BaseAgent

        def _patched_setup_logger(self) -> logging.Logger:      # noqa: ANN001
            return get_logger(self.name)

        BaseAgent._setup_logger = _patched_setup_logger
    except ImportError:
        pass  # agents package not yet importable — skip silently
