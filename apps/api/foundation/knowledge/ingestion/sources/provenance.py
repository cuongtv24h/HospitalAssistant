import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from ..models import SourceRecord
from .markdown_loader import read_markdown

DEFAULT_MANIFEST_PATH = Path("hospital_assistant/data/knowledge/section_1/manifest.json")

def load_manifest(manifest_path: Path = None, root_dir: Path = None) -> Dict[str, Any]:
    if manifest_path is None:
        manifest_path = DEFAULT_MANIFEST_PATH
    if root_dir is not None and not manifest_path.is_absolute():
        manifest_path = root_dir / manifest_path
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def normalize_source_record(
    entry: Dict[str, Any],
    root_dir: Path,
    manifest: Optional[Dict[str, Any]] = None
) -> Tuple[SourceRecord, List[str]]:
    warnings_and_errors = []
    
    sid = entry.get("source_id", "")
    kind = entry.get("source_kind", "web")
    ingest_rel = entry.get("ingestion_path", "")
    full_path = root_dir / ingest_rel if ingest_rel else None

    body_text = ""
    fm = {}
    if full_path and full_path.exists():
        fm, body_text = read_markdown(full_path)
        computed_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()
    else:
        computed_hash = ""
        warnings_and_errors.append(f"Source file not found: {full_path}")

    # Cross-check manifest if available and source_kind == 'web'
    manifest_source = None
    if manifest and kind == "web":
        if fm.get("citation_id") != sid:
            warnings_and_errors.append(
                f"Citation ID mismatch for {sid}: frontmatter={fm.get('citation_id')}"
            )
        for src in manifest.get("sources", []):
            if src.get("citation_id") == sid or src.get("document") == Path(ingest_rel).name:
                manifest_source = src
                break
        if manifest_source:
            # Check for mismatches
            if fm.get("source_url") and manifest_source.get("source_url") and fm["source_url"] != manifest_source["source_url"]:
                warnings_and_errors.append(
                    f"URL mismatch for {sid}: frontmatter={fm['source_url']} vs manifest={manifest_source['source_url']}"
                )
            if fm.get("content_sha256") and manifest_source.get("content_sha256") and fm["content_sha256"] != manifest_source["content_sha256"]:
                warnings_and_errors.append(
                    f"Hash mismatch for {sid}: frontmatter={fm['content_sha256']} vs manifest={manifest_source['content_sha256']}"
                )
            if bool(fm.get("extraction_incomplete", False)) != bool(manifest_source.get("extraction_incomplete", False)):
                warnings_and_errors.append(
                    f"Extraction status mismatch for {sid}: frontmatter={fm.get('extraction_incomplete')} "
                    f"vs manifest={manifest_source.get('extraction_incomplete')}"
                )
        else:
            warnings_and_errors.append(f"Manifest entry missing for {sid}")

        registry_url = entry.get("source_url")
        if registry_url and fm.get("source_url") != registry_url:
            warnings_and_errors.append(
                f"Registry URL mismatch for {sid}: frontmatter={fm.get('source_url')} vs registry={registry_url}"
            )

    title = fm.get("title") or entry.get("title") or sid
    publisher = fm.get("publisher") or entry.get("publisher") or "Bệnh viện Tim Hà Nội"
    topic = fm.get("topic") or entry.get("topic") or "general"
    crawled_at = fm.get("crawled_at") or entry.get("crawled_at")
    
    if kind == "web":
        display_name = title
        source_url = fm.get("source_url") or entry.get("source_url")
        effective_date = None
        incomplete = bool(entry.get("extraction_incomplete", fm.get("extraction_incomplete", False)))
    else:
        # Document source
        display_name = entry.get("display_name", f"{title}.pdf")
        source_url = None
        effective_date = entry.get("effective_date", "2026-01-01")
        crawled_at = None
        incomplete = bool(entry.get("extraction_incomplete", False))

    quality_flags = []
    if incomplete:
        quality_flags.append("extraction_incomplete")
    if not body_text or len(body_text.strip()) < 50:
        quality_flags.append("low_content")

    source_hash = fm.get("content_sha256") or entry.get("source_content_hash") or computed_hash

    record = SourceRecord(
        source_id=sid,
        source_kind=kind,
        title=title,
        display_name=display_name,
        source_url=source_url,
        ingestion_path=ingest_rel,
        publisher=publisher,
        topic=topic,
        domain_code=topic,
        version=entry.get("version", "1.0"),
        approval_status="approved",
        effective_date=effective_date,
        crawled_at=crawled_at,
        source_content_hash=source_hash,
        extraction_incomplete=incomplete,
        quality_flags=quality_flags,
        is_mock=False,
        ingestible=not incomplete,
        # Authoritative releases are always staged inactive. Activation is a
        # separate, transactional database operation.
        is_active=False,
    )

    return record, warnings_and_errors
