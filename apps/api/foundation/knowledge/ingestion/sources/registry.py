# === TASK:WP-008:START ===
import json
from pathlib import Path
from typing import List, Dict, Any
from ..models import SourceRecord

ROOT = Path(__file__).resolve().parents[6]
SEED_DIR = ROOT / "data" / "mvp" / "seed"

def load_seed_registry() -> Dict[str, Any]:
    path = SEED_DIR / "source-registry.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_knowledge_base() -> Dict[str, Any]:
    path = SEED_DIR / "knowledge-base.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_authoritative_registry(path: Path = None) -> Dict[str, Any]:
    if path is None:
        path = SEED_DIR / "authoritative-source-registry.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_authoritative_registry(registry: Dict[str, Any], root_dir: Path = None) -> List[str]:
    if root_dir is None:
        root_dir = ROOT

    errors = []
    sources = registry.get("sources", [])
    if len(sources) != 25:
        errors.append(f"Authoritative registry must contain exactly 25 sources, found {len(sources)}")

    seen_ids = set()
    for idx, src in enumerate(sources):
        sid = src.get("source_id", "")
        if not sid:
            errors.append(f"Source at index {idx} missing source_id")
        elif sid in seen_ids:
            errors.append(f"Duplicate source_id found: {sid}")
        else:
            seen_ids.add(sid)

        if sid.startswith("SRC-MOCK-") or src.get("is_mock"):
            errors.append(f"Mock source {sid} not allowed in authoritative registry")

        kind = src.get("source_kind", "")
        if kind not in ("web", "document"):
            errors.append(f"Invalid source_kind '{kind}' for source {sid}")

        url = src.get("source_url")
        if kind == "web":
            if not url or not (url.startswith("http://") or url.startswith("https://")):
                errors.append(f"Web source {sid} missing valid HTTP(S) source_url: {url}")
        elif kind == "document":
            if url is not None:
                errors.append(f"Document source {sid} should have null source_url, got {url}")
            display_name = src.get("display_name", "")
            if not display_name or not display_name.endswith(".pdf"):
                errors.append(f"Document source {sid} missing valid PDF display_name: {display_name}")

        ingest_path = src.get("ingestion_path")
        if not ingest_path:
            errors.append(f"Source {sid} missing ingestion_path")
        else:
            full_path = root_dir / ingest_path
            if not full_path.exists():
                errors.append(f"Source {sid} ingestion_path does not exist: {full_path}")

    return errors


def get_eligible_sources(registry: Dict[str, Any] = None) -> List[SourceRecord]:
    if registry is None:
        registry = load_seed_registry()
        
    sources = []
    for src in registry.get("sources", []):
        sources.append(SourceRecord(
            source_id=src.get("source_id", ""),
            title=src.get("title", ""),
            source_type=src.get("source_type", ""),
            path=src.get("path"),
            domain_code=src.get("domain_code", ""),
            version=src.get("version", "1.0"),
            approval_status=src.get("approval_status", ""),
            effective_date=src.get("effective_date", ""),
            is_mock=src.get("is_mock", False),
            ingestible=src.get("ingestible", True),
            is_active=src.get("is_active", True)
        ))
    return sources

# === TASK:WP-008:END ===
