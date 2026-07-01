"""
Validators

All input-validation logic for GRaC in one place.

Every validator follows the same pattern:
- Returns ``True`` / ``False`` for soft checks (``is_*`` / ``has_*``).
- Raises ``ValidationError`` for hard checks (``validate_*``).

Keeping validation here means agents and the API share identical rules
and error messages — no duplication, no drift.

Usage:
    from utils.validators import validate_sector, validate_query, validate_file_upload
    from utils.validators import ValidationError

    validate_sector("fintech")                  # raises if bad
    validate_query("What is Section 5?")        # raises if too short/long
    validate_file_upload("/tmp/policy.pdf")     # raises if wrong type or missing

    # Soft checks
    from utils.validators import is_valid_sector, is_supported_audio
    if is_valid_sector("healthcare"):           # → False (disabled)
        ...
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ValidationError(ValueError):
    """
    Raised when a GRaC input fails validation.

    Carries a ``field`` attribute so API error responses can point at the
    exact request field that was rejected.
    """

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.field = field

    def to_dict(self) -> dict:
        """Serialise to a dict suitable for a JSON API error response."""
        d: dict = {"error": "validation_error", "message": str(self)}
        if self.field:
            d["field"] = self.field
        return d


# ---------------------------------------------------------------------------
# Sector validators
# ---------------------------------------------------------------------------

def validate_sector(sector: Any, *, require_enabled: bool = True) -> str:
    """
    Assert *sector* is a non-empty string naming a known (and enabled) sector.

    Args:
        sector: Value to validate — expected to be a string.
        require_enabled: If True (default), also reject disabled sectors.

    Returns:
        The validated sector ID (stripped).

    Raises:
        ValidationError: If the sector is missing, wrong type, unknown,
            or disabled.
    """
    if not isinstance(sector, str) or not sector.strip():
        raise ValidationError(
            "sector must be a non-empty string.",
            field="sector",
        )

    sector = sector.strip().lower()

    try:
        from utils.sector_manager import sector_manager
        sector_manager.validate_sector(sector, require_enabled=require_enabled)
    except ValueError as exc:
        raise ValidationError(str(exc), field="sector") from exc

    return sector


def is_valid_sector(sector: Any, *, require_enabled: bool = True) -> bool:
    """Return True if *sector* passes ``validate_sector`` without raising."""
    try:
        validate_sector(sector, require_enabled=require_enabled)
        return True
    except ValidationError:
        return False


# ---------------------------------------------------------------------------
# Query / text validators
# ---------------------------------------------------------------------------

# Absolute limits — intentionally generous; real content should stay well under
QUERY_MIN_CHARS   = 5
QUERY_MAX_CHARS   = 4_000
POLICY_MIN_CHARS  = 50
POLICY_MAX_CHARS  = 500_000   # ~100 pages of dense text


def validate_query(query: Any, *, field: str = "query") -> str:
    """
    Validate a user compliance query string.

    Rules:
    - Must be a non-empty string.
    - Must be at least ``QUERY_MIN_CHARS`` characters (not just whitespace).
    - Must not exceed ``QUERY_MAX_CHARS`` characters.
    - Must not be purely numeric or purely punctuation (catches accidents).

    Returns:
        Stripped query string.

    Raises:
        ValidationError
    """
    if not isinstance(query, str):
        raise ValidationError(
            f"{field} must be a string, got {type(query).__name__}.",
            field=field,
        )

    stripped = query.strip()

    if len(stripped) < QUERY_MIN_CHARS:
        raise ValidationError(
            f"{field} is too short (minimum {QUERY_MIN_CHARS} characters).",
            field=field,
        )

    if len(stripped) > QUERY_MAX_CHARS:
        raise ValidationError(
            f"{field} is too long (maximum {QUERY_MAX_CHARS} characters; "
            f"got {len(stripped)}).",
            field=field,
        )

    # Reject queries that contain only digits/punctuation — almost always a mistake
    if re.fullmatch(r"[\d\s\W]+", stripped):
        raise ValidationError(
            f"{field} must contain at least some alphabetic text.",
            field=field,
        )

    return stripped


def validate_policy_text(text: Any, *, field: str = "policy") -> str:
    """
    Validate a full policy document text.

    More permissive length limits than ``validate_query`` — a real policy
    is expected to be long.

    Returns:
        Stripped text.

    Raises:
        ValidationError
    """
    if not isinstance(text, str):
        raise ValidationError(
            f"{field} must be a string, got {type(text).__name__}.",
            field=field,
        )

    stripped = text.strip()

    if len(stripped) < POLICY_MIN_CHARS:
        raise ValidationError(
            f"{field} text is too short to analyse "
            f"(minimum {POLICY_MIN_CHARS} characters; got {len(stripped)}).",
            field=field,
        )

    if len(stripped) > POLICY_MAX_CHARS:
        raise ValidationError(
            f"{field} text is too large (maximum {POLICY_MAX_CHARS} characters; "
            f"got {len(stripped)}). Consider splitting into smaller sections.",
            field=field,
        )

    return stripped


# ---------------------------------------------------------------------------
# File-type / upload validators
# ---------------------------------------------------------------------------

SUPPORTED_PDF_EXTENSIONS   = {".pdf"}
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".webm", ".ogg", ".flac"}
SUPPORTED_DOC_EXTENSIONS   = {".pdf", ".txt", ".docx"}

# Size limits
MAX_PDF_BYTES   = 50 * 1024 * 1024   # 50 MB
MAX_AUDIO_BYTES = 25 * 1024 * 1024   # 25 MB (Whisper API limit)


def validate_pdf_path(path: Any, *, field: str = "pdf_path") -> Path:
    """
    Validate that *path* points to an existing readable PDF file.

    Checks:
    - Not empty, must be a string or Path.
    - File must exist.
    - Extension must be ``.pdf``.
    - File must not be empty.
    - File size must not exceed ``MAX_PDF_BYTES``.

    Returns:
        Resolved ``Path`` object.

    Raises:
        ValidationError
    """
    return _validate_file_path(
        path,
        field=field,
        allowed_extensions=SUPPORTED_PDF_EXTENSIONS,
        max_bytes=MAX_PDF_BYTES,
        type_label="PDF",
    )


def validate_audio_path(path: Any, *, field: str = "audio_path") -> Path:
    """
    Validate that *path* points to an existing, supported audio file.

    Supported formats: mp3, mp4, wav, m4a, webm, ogg, flac.
    Max size: 25 MB (Whisper API hard limit).

    Returns:
        Resolved ``Path`` object.

    Raises:
        ValidationError
    """
    return _validate_file_path(
        path,
        field=field,
        allowed_extensions=SUPPORTED_AUDIO_EXTENSIONS,
        max_bytes=MAX_AUDIO_BYTES,
        type_label="audio",
    )


def validate_file_upload(path: Any, *, field: str = "file") -> Path:
    """
    General-purpose upload validator (PDF, text, or DOCX).

    Returns:
        Resolved ``Path``.

    Raises:
        ValidationError
    """
    return _validate_file_path(
        path,
        field=field,
        allowed_extensions=SUPPORTED_DOC_EXTENSIONS,
        max_bytes=MAX_PDF_BYTES,
        type_label="document",
    )


def is_supported_audio(path: Any) -> bool:
    """Return True if *path* is an existing, supported audio file."""
    try:
        validate_audio_path(path)
        return True
    except ValidationError:
        return False


def is_supported_pdf(path: Any) -> bool:
    """Return True if *path* is an existing PDF file."""
    try:
        validate_pdf_path(path)
        return True
    except ValidationError:
        return False


# ---------------------------------------------------------------------------
# API / supervisor payload validators
# ---------------------------------------------------------------------------

VALID_REQUEST_TYPES = frozenset({
    "pdf_analysis",
    "voice_input",
    "compliance_question",
    "scoring",
})

VALID_DOC_TYPES = frozenset({
    "gap_analysis",
    "incident_report",
    "policy_draft",
})

VALID_OUTPUT_FORMATS = frozenset({"pdf", "docx"})


def validate_supervisor_payload(payload: Any) -> dict:
    """
    Validate the top-level request payload sent to ``SupervisorAgent.run()``.

    Expected shape::

        {
            "request_type": "pdf_analysis" | "voice_input" |
                            "compliance_question" | "scoring",
            "data":         <any>,
            "sector":       "cybersecurity",   # optional
            "options":      {}                 # optional
        }

    Returns:
        The validated payload dict (sector normalised to lowercase).

    Raises:
        ValidationError: For any missing or malformed field.
    """
    if not isinstance(payload, dict):
        raise ValidationError(
            f"Request payload must be a JSON object, got {type(payload).__name__}."
        )

    # request_type
    request_type = payload.get("request_type")
    if not request_type:
        raise ValidationError("'request_type' is required.", field="request_type")
    if request_type not in VALID_REQUEST_TYPES:
        raise ValidationError(
            f"Unknown request_type '{request_type}'. "
            f"Valid values: {sorted(VALID_REQUEST_TYPES)}",
            field="request_type",
        )

    # data
    if "data" not in payload or payload["data"] is None:
        raise ValidationError("'data' is required.", field="data")

    # sector (optional — validated only when present)
    if "sector" in payload and payload["sector"] is not None:
        payload["sector"] = validate_sector(payload["sector"])

    # options (optional dict)
    if "options" in payload and not isinstance(payload.get("options"), dict):
        raise ValidationError("'options' must be a JSON object.", field="options")

    return payload


def validate_doc_type(doc_type: Any, *, field: str = "type") -> str:
    """
    Validate a document type string for the WriterAgent.

    Returns:
        Validated doc_type string.

    Raises:
        ValidationError
    """
    if not isinstance(doc_type, str) or not doc_type.strip():
        raise ValidationError(f"'{field}' must be a non-empty string.", field=field)

    if doc_type.strip() not in VALID_DOC_TYPES:
        raise ValidationError(
            f"Unknown document type '{doc_type}'. "
            f"Valid types: {sorted(VALID_DOC_TYPES)}",
            field=field,
        )
    return doc_type.strip()


def validate_output_format(fmt: Any, *, field: str = "format") -> str:
    """
    Validate a requested output format (``"pdf"`` or ``"docx"``).

    Returns:
        Validated format string.

    Raises:
        ValidationError
    """
    if not isinstance(fmt, str) or fmt.strip().lower() not in VALID_OUTPUT_FORMATS:
        raise ValidationError(
            f"'{field}' must be one of: {sorted(VALID_OUTPUT_FORMATS)}. Got: {fmt!r}",
            field=field,
        )
    return fmt.strip().lower()


def validate_top_k(top_k: Any, *, field: str = "top_k") -> int:
    """
    Validate the ``top_k`` parameter for the RetrieverAgent (1–20).

    Returns:
        Validated integer.

    Raises:
        ValidationError
    """
    try:
        value = int(top_k)
    except (TypeError, ValueError):
        raise ValidationError(
            f"'{field}' must be an integer, got {top_k!r}.",
            field=field,
        )

    if not (1 <= value <= 20):
        raise ValidationError(
            f"'{field}' must be between 1 and 20, got {value}.",
            field=field,
        )
    return value


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_file_path(
    path: Any,
    *,
    field: str,
    allowed_extensions: set[str],
    max_bytes: int,
    type_label: str,
) -> Path:
    """Shared implementation for all file-path validators."""
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValidationError(
            f"'{field}' must be a non-empty file path.",
            field=field,
        )

    resolved = Path(path).resolve()

    if not resolved.exists():
        raise ValidationError(
            f"'{field}': file not found at '{resolved}'.",
            field=field,
        )

    if not resolved.is_file():
        raise ValidationError(
            f"'{field}': path exists but is not a file: '{resolved}'.",
            field=field,
        )

    ext = resolved.suffix.lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            f"'{field}': unsupported {type_label} format '{ext}'. "
            f"Supported: {sorted(allowed_extensions)}",
            field=field,
        )

    size = resolved.stat().st_size
    if size == 0:
        raise ValidationError(
            f"'{field}': file is empty: '{resolved}'.",
            field=field,
        )

    if size > max_bytes:
        mb = size / (1024 * 1024)
        max_mb = max_bytes / (1024 * 1024)
        raise ValidationError(
            f"'{field}': file is too large ({mb:.1f} MB; "
            f"maximum is {max_mb:.0f} MB).",
            field=field,
        )

    return resolved
