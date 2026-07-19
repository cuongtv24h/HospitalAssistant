#!/usr/bin/env python3
"""Verify a staged/active authoritative corpus and optionally mark it verified."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.foundation.knowledge.ingestion.persistence.postgres import psycopg_connection_url, redact_connection_url
from apps.api.foundation.knowledge.ingestion.sources.registry import (
    load_authoritative_registry,
    validate_authoritative_registry,
)
from apps.api.foundation.knowledge.repository.lexical_search import build_sparse_tsquery


GOLDEN_QUERIES = (
    ("đặt lịch khám", "dat_lich", None),
    ("quy trình đón tiếp", "quy_trinh", None),
    ("bảo hiểm y tế BHYT", "bhyt", None),
    ("giá dịch vụ kỹ thuật", "gia_dich_vu", None),
    ("bác sĩ chuyên khoa", "bac_si_khoa", None),
    # The only selected schedule source is extraction-incomplete. Cover this
    # topic by proving it cannot be returned as factual evidence.
    ("lịch khám giờ làm việc", None, "HHH-SCH-001"),
    ("Bệnh viện Tim Hà Nội", "thong_tin_benh_vien", None),
)


def _database_checks(cursor, release_id: str, allowed_ids: set[str], expect_active: bool) -> tuple[list[str], dict]:
    errors: list[str] = []
    cursor.execute(
        "SELECT status, expected_source_count, expected_chunk_count, embedding_identity, prior_release_id "
        "FROM corpus_releases WHERE release_id = %s",
        (release_id,),
    )
    release = cursor.fetchone()
    if not release:
        return [f"Release {release_id} does not exist."], {}
    status, expected_sources, expected_chunks, embedding_identity, prior_release_id = release
    allowed_statuses = {"active"} if expect_active else {"staged", "verified"}
    if status not in allowed_statuses:
        errors.append(f"Release status is {status}; expected one of {sorted(allowed_statuses)}.")

    cursor.execute(
        """
        SELECT source_id, metadata, is_active, vector_dims(embedding)
          FROM knowledge_chunks
         WHERE metadata->>'corpus_release_id' = %s
        """,
        (release_id,),
    )
    rows = cursor.fetchall()
    source_ids = {row[0] for row in rows}
    if source_ids != allowed_ids:
        errors.append(
            f"Source mismatch: missing={sorted(allowed_ids - source_ids)}, "
            f"unauthorized={sorted(source_ids - allowed_ids)}"
        )
    if len(rows) != expected_chunks:
        errors.append(f"Chunk count is {len(rows)}; release expects {expected_chunks}.")
    if expected_sources != 25:
        errors.append(f"Release expects {expected_sources} sources instead of 25.")

    required_metadata = {
        "external_chunk_id", "source_id", "source_kind", "title", "display_name",
        "ingestion_path", "publisher", "source_content_hash", "content_hash",
        "chunker_version", "tokenizer", "embedding_identity", "corpus_release_id",
        "answerable", "extraction_incomplete",
    }
    incomplete_count = 0
    for source_id, metadata, is_active, dimensions in rows:
        metadata = metadata if isinstance(metadata, dict) else json.loads(metadata or "{}")
        missing = sorted(key for key in required_metadata if key not in metadata)
        if missing:
            errors.append(f"Chunk from {source_id} is missing metadata: {', '.join(missing)}")
        if str(source_id).startswith("SRC-MOCK-") or metadata.get("is_mock"):
            errors.append(f"Mock evidence found in release: {source_id}")
        if metadata.get("source_kind") == "web" and not str(metadata.get("source_url", "")).startswith(("http://", "https://")):
            errors.append(f"Web source {source_id} has no canonical HTTP(S) URL.")
        if metadata.get("source_kind") == "document":
            if metadata.get("source_url") is not None or not str(metadata.get("display_name", "")).endswith(".pdf"):
                errors.append(f"Document source {source_id} has invalid PDF citation metadata.")
        if metadata.get("extraction_incomplete"):
            incomplete_count += 1
            if metadata.get("answerable") is not False:
                errors.append(f"Incomplete source {source_id} is marked answerable.")
        if dimensions != 1024:
            errors.append(f"Chunk from {source_id} has vector dimension {dimensions}, expected 1024.")
        if bool(is_active) != expect_active:
            errors.append(f"Chunk active-state mismatch for {source_id}.")

    cursor.execute("SELECT count(*) FROM corpus_releases WHERE status = 'active'")
    active_release_count = cursor.fetchone()[0]
    if active_release_count > 1:
        errors.append("More than one corpus release is active.")

    report = {
        "release_id": release_id,
        "status": status,
        "source_count": len(source_ids),
        "chunk_count": len(rows),
        "incomplete_chunk_count": incomplete_count,
        "embedding_identity": embedding_identity,
        "vector_dimensions": 1024,
        "prior_release_id": prior_release_id,
        "active_release_count": active_release_count,
    }
    return errors, report


def _golden_checks(cursor, release_id: str) -> tuple[list[str], list[dict]]:
    errors: list[str] = []
    results: list[dict] = []
    for text, expected_domain, excluded_source_id in GOLDEN_QUERIES:
        sparse = build_sparse_tsquery(text)
        cursor.execute(
            """
            SELECT domain.domain_code, chunk.source_id,
                   chunk.metadata->>'display_name', chunk.metadata->>'source_url'
              FROM knowledge_chunks AS chunk
              JOIN knowledge_domains AS domain ON domain.domain_id = chunk.domain_id
             WHERE chunk.metadata->>'corpus_release_id' = %s
               AND COALESCE((chunk.metadata->>'answerable')::boolean, false) IS TRUE
               AND chunk.search_document @@ to_tsquery('simple', %s)
             ORDER BY ts_rank_cd(chunk.search_document, to_tsquery('simple', %s), 32) DESC
             LIMIT 5
            """,
            (release_id, sparse, sparse),
        )
        rows = cursor.fetchall()
        domains = {row[0] for row in rows}
        top_sources = [row[1] for row in rows]
        results.append({
            "query": text,
            "expected_domain": expected_domain,
            "excluded_source_id": excluded_source_id,
            "top_sources": top_sources,
        })
        if expected_domain is not None and expected_domain not in domains:
            errors.append(f"Golden query '{text}' did not retrieve domain {expected_domain} in top 5.")
        if excluded_source_id is not None and excluded_source_id in top_sources:
            errors.append(
                f"Golden query '{text}' retrieved incomplete source {excluded_source_id}."
            )
    return errors, results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--expect-active", action="store_true")
    parser.add_argument("--mark-verified", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--report", type=Path, help="Write a redacted JSON migration report")
    args = parser.parse_args()

    registry = load_authoritative_registry()
    errors = validate_authoritative_registry(registry, root_dir=ROOT)
    if errors:
        print("Registry verification failed:\n- " + "\n- ".join(errors))
        return 1
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise SystemExit("DATABASE_URL is required for release verification.")
    if args.mark_verified and (args.expect_active or not args.yes):
        raise SystemExit("Use --mark-verified --yes only for a staged release.")

    print(f"Database target: {redact_connection_url(database_url)}")
    import psycopg
    with psycopg.connect(
        psycopg_connection_url(database_url), prepare_threshold=None
    ) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                allowed_ids = {source["source_id"] for source in registry["sources"]}
                db_errors, report = _database_checks(cursor, args.release_id, allowed_ids, args.expect_active)
                golden_errors, golden_results = _golden_checks(cursor, args.release_id)
                errors.extend(db_errors)
                errors.extend(golden_errors)
                report["golden_queries"] = golden_results
                report["verification_passed"] = not errors
                if errors:
                    print("Verification FAILED:\n- " + "\n- ".join(errors))
                    return 1
                if args.mark_verified:
                    cursor.execute(
                        """
                        UPDATE corpus_releases
                           SET status = 'verified', verified_at = now(), verification_report = %s::jsonb
                         WHERE release_id = %s AND status IN ('staged', 'verified')
                        """,
                        (json.dumps(report, ensure_ascii=False), args.release_id),
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError("Release could not be marked verified.")

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
        print(f"Redacted report written to {args.report}")
    print(rendered)
    print("Verification PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
