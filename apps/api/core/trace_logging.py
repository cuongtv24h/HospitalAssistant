"""PII-safe structured timing logs shared by agent, RAG, and providers."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger("uvicorn.error")


def trace_event(
    event: str,
    *,
    trace_id: Optional[str] = None,
    started_at: Optional[float] = None,
    **fields: Any,
) -> None:
    """Emit a structured, PII-safe timing event to the application logger."""
    payload = {"event": event, "trace_id": trace_id, **fields}
    if started_at is not None:
        payload["elapsed_ms"] = round((time.monotonic() - started_at) * 1000, 2)
    logger.info("agent_trace %s", json.dumps(payload, ensure_ascii=False, default=str))
