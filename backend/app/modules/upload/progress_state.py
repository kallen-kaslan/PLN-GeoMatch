"""In-memory progress tracking for upload ingestion and mapping validation."""

from typing import Any

UPLOAD_PROGRESS: dict[str | int, dict[str, Any]] = {}
