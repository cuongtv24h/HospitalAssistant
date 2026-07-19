#!/usr/bin/env python3
"""Validate, stage, activate, or roll back the authoritative 25-source corpus."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.foundation.knowledge.ingestion.chunking.structure_chunker import chunk_source_record
from apps.api.foundation.knowledge.ingestion.embeddings.factory import get_embedding_provider
from apps.api.foundation.knowledge.ingestion.models import ChunkRecord, IngestionResult, SourceRecord
from apps.api.foundation.knowledge.ingestion.persistence.postgres import (
    activate_release,
    build_import_plan,
    check_preflight_dimensions,
    delete_stale_staged_chunks,
    mark_release_staged,
    persist_batch,
    psycopg_connection_url,
    redact_connection_url,
    register_staging_release,
    rollback_release,
    upsert_domain,
)
from apps.api.foundation.knowledge.ingestion.reporting import generate_dry_run_report
from apps.api.foundation.knowledge.ingestion.settings import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
)
from apps.api.foundation.knowledge.ingestion.sources.markdown_loader import read_markdown
from apps.api.foundation.knowledge.ingestion.sources.provenance import load_manifest, normalize_source_record
from apps.api.foundation.knowledge.ingestion.sources.registry import (
    load_authoritative_registry,
    validate_authoritative_registry,
)
from apps.api.foundation.knowledge.ingestion.validation.chunk_validator import validate_chunk
from apps.api.foundation.knowledge.ingestion.validation.embedding_validator import validate_embedding
from apps.api.foundation.knowledge.ingestion.validation.source_validator import validate_source


DOMAIN_MAPPING = {
    "general": "thong_tin_benh_vien",
    "appointment": "dat_lich",
    "procedure": "quy_trinh",
    "insurance": "bhyt",
    "pricing": "gia_dich_vu",
    "schedule": "gio_lam_viec",
    "organization": "thong_tin_benh_vien",
    "service": "bac_si_khoa",
    "doctors_departments": "bac_si_khoa",
}

DOMAIN_NAMES = {
    "thong_tin_benh_vien": "Thông tin bệnh viện",
    "dat_lich": "Đặt lịch khám",
    "quy_trinh": "Quy trình khám",
    "bhyt": "Bảo hiểm y tế",
    "gia_dich_vu": "Giá dịch vụ",
    "gio_lam_viec": "Giờ làm việc",
    "bac_si_khoa": "Bác sĩ và chuyên khoa",
}


def _prepare_corpus(release_id: str) -> Tuple[dict, List[SourceRecord], List[ChunkRecord], List[str]]:
    registry = load_authoritative_registry()
    errors = validate_authoritative_registry(registry, root_dir=ROOT)
    if errors:
        return registry, [], [], errors

    allowed_source_ids = {source["source_id"] for source in registry["sources"]}
    manifest = load_manifest(root_dir=ROOT)
    source_records: List[SourceRecord] = []
    chunks: List[ChunkRecord] = []
    for entry in registry["sources"]:
        source, provenance_issues = normalize_source_record(entry, root_dir=ROOT, manifest=manifest)
        errors.extend(provenance_issues)
        source.domain_code = DOMAIN_MAPPING.get(source.topic, source.topic)
        errors.extend(validate_source(source, allowed_source_ids=allowed_source_ids))

        # read_markdown returns the evidence body with YAML front matter removed.
        _, body = read_markdown(ROOT / entry["ingestion_path"])
        generated = chunk_source_record(source, body, release_id=release_id)
        for chunk in generated:
            errors.extend(validate_chunk(chunk))
        source_records.append(source)
        chunks.extend(generated)

    if {chunk.source_id for chunk in chunks} != allowed_source_ids:
        errors.append("Every selected source must produce at least one auditable chunk.")
    if any(chunk.is_mock for chunk in chunks):
        errors.append("Mock chunks are forbidden in an authoritative release.")
    return registry, source_records, chunks, errors


def _embed_records(records: List[ChunkRecord]) -> List[Tuple[ChunkRecord, List[float]]]:
    provider = get_embedding_provider(EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS)
    output: List[Tuple[ChunkRecord, List[float]]] = []
    for start in range(0, len(records), EMBEDDING_BATCH_SIZE):
        batch = records[start : start + EMBEDDING_BATCH_SIZE]
        vectors = provider.embed_batch([record.embedding_text for record in batch])
        if len(vectors) != len(batch):
            raise RuntimeError("Embedding provider returned an incomplete batch.")
        for record, vector in zip(batch, vectors):
            validate_embedding(vector, EMBEDDING_DIMENSIONS)
            output.append((record, vector))
        print(f"Embedded {min(start + len(batch), len(records))}/{len(records)} chunks")
    return output


def _confirm_write(args: argparse.Namespace, operation: str) -> None:
    if not args.yes:
        raise SystemExit(f"{operation} changes the database; rerun with --yes after reviewing the command.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--dry-run", action="store_true")
    actions.add_argument("--stage", action="store_true")
    actions.add_argument("--activate", action="store_true")
    actions.add_argument("--rollback", action="store_true")
    parser.add_argument("--release-id", help="Stable operator-selected release ID")
    parser.add_argument("--prior-release-id", help="Verified prior release used for rollback")
    parser.add_argument("--yes", action="store_true", help="Confirm a database write")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "")
    release_id = args.release_id or f"dry-run-{int(time.time())}"
    if (args.stage or args.activate or args.rollback) and not args.release_id:
        parser.error("--release-id is required for stage, activate, and rollback operations")

    print(f"Database target: {redact_connection_url(database_url)}")
    registry, sources, chunks, errors = _prepare_corpus(release_id)
    result = IngestionResult(
        total_chunks=len(chunks),
        answerable_chunks=sum(chunk.answerable for chunk in chunks),
        mock_chunks=sum(chunk.is_mock for chunk in chunks),
        approved_chunks=sum(chunk.approval_status in {"approved", "approved_for_pilot"} for chunk in chunks),
        errors=errors,
        chunk_records=chunks,
    )
    print(generate_dry_run_report(result, sources_processed=sources))
    if errors:
        print("Validation failed; no database changes were made.")
        return 1
    if args.dry_run or not (args.stage or args.activate or args.rollback):
        print("Dry run completed successfully. No database changes were made.")
        return 0
    if not database_url:
        raise SystemExit("DATABASE_URL is required for database operations.")

    _confirm_write(args, "This operation")
    import psycopg

    allowed_source_ids = {source["source_id"] for source in registry["sources"]}
    embedding_identity = f"{EMBEDDING_PROVIDER}:{EMBEDDING_MODEL}:{EMBEDDING_DIMENSIONS}"
    with psycopg.connect(
        psycopg_connection_url(database_url), prepare_threshold=None
    ) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                check_preflight_dimensions(cursor, EMBEDDING_DIMENSIONS)
                if args.stage:
                    register_staging_release(
                        cursor, release_id, len(allowed_source_ids), len(chunks), embedding_identity
                    )
                    domain_map: Dict[str, str] = {}
                    for domain_code in sorted({chunk.domain for chunk in chunks}):
                        domain_map[domain_code] = upsert_domain(
                            cursor, domain_code, DOMAIN_NAMES.get(domain_code, domain_code), "content_admin"
                        )
                    plan = build_import_plan(
                        cursor, chunks, EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS
                    )
                    changed = plan.to_insert + plan.to_update
                    persist_batch(cursor, _embed_records(changed), domain_map)
                    delete_stale_staged_chunks(cursor, release_id, plan.to_retire)
                    mark_release_staged(cursor, release_id)
                    print(
                        f"Staged release {release_id}: inserted={len(plan.to_insert)}, "
                        f"updated={len(plan.to_update)}, skipped={len(plan.to_skip)}, "
                        f"retired_stale={len(plan.to_retire)}. Nothing was activated."
                    )
                elif args.activate:
                    activated, retired = activate_release(cursor, release_id, allowed_source_ids)
                    print(f"Activated {release_id}: activated={activated}, retired_previous={retired}.")
                else:
                    if not args.prior_release_id:
                        parser.error("--prior-release-id is required for rollback")
                    reactivated, deactivated = rollback_release(
                        cursor, args.prior_release_id, release_id
                    )
                    print(
                        f"Rolled back {release_id} to {args.prior_release_id}: "
                        f"reactivated={reactivated}, deactivated={deactivated}."
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
