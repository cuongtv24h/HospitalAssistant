# === TASK:WP-008:START ===
from pathlib import Path
from typing import List, Set, Optional
from ..models import SourceRecord
from ..errors import ValidationError

ROOT = Path(__file__).resolve().parents[6]

def validate_source(src: SourceRecord, allowed_source_ids: Optional[Set[str]] = None) -> List[str]:
    errors = []
    if not src.source_id:
        errors.append("Source missing source_id")

    if allowed_source_ids is not None and src.source_id not in allowed_source_ids:
        errors.append(f"Unauthorized source_id '{src.source_id}' not in authoritative catalog")

    if src.is_mock or src.source_id.startswith("SRC-MOCK-"):
        errors.append(f"Mock source {src.source_id} not allowed in authoritative pipeline")

    if not src.title:
        errors.append(f"Source {src.source_id} missing title")

    if not src.display_name:
        errors.append(f"Source {src.source_id} missing display_name")

    if src.source_kind == "web":
        if not src.source_url or not (src.source_url.startswith("http://") or src.source_url.startswith("https://")):
            errors.append(f"Web source {src.source_id} missing valid HTTP(S) source_url: {src.source_url}")
    elif src.source_kind == "document":
        if src.source_url is not None:
            errors.append(f"Document source {src.source_id} must have null source_url, got {src.source_url}")
        if not src.display_name.endswith(".pdf"):
            errors.append(f"Document source {src.source_id} display_name must end with .pdf: {src.display_name}")
    else:
        errors.append(f"Source {src.source_id} invalid source_kind: {src.source_kind}")

    if src.ingestion_path:
        full_path = ROOT / src.ingestion_path
        if not full_path.is_file():
            errors.append(f"Source {src.source_id} ingestion_path not found: {src.ingestion_path}")
    else:
        errors.append(f"Source {src.source_id} missing ingestion_path")

    return errors
# === TASK:WP-008:END ===
