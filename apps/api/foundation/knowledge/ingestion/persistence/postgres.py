"""PostgreSQL persistence for versioned authoritative corpus releases."""

from __future__ import annotations

import datetime
import json
import re
from typing import Any, Dict, List, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..errors import IngestionError, ValidationError
from ..models import ChunkRecord, ImportPlan
from .mapper import map_chunk_to_row, persistence_uuid_for


def redact_connection_url(url: str) -> str:
    """Return a log-safe database identity without credentials or query data."""
    if not url:
        return "<unset>"
    match = re.match(r"^[a-zA-Z0-9+.-]+://(?:[^@]+@)?([^/:?]+)(?::(\d+))?/([^?]+)", url)
    if not match:
        return "<redacted-database-url>"
    host, port, database = match.groups()
    return f"postgresql://***@{host}{':' + port if port else ''}/{database}"


def psycopg_connection_url(url: str) -> str:
    """Remove client-specific URL options that libpq does not understand."""
    if not url:
        return url
    parts = urlsplit(url)
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "pgbouncer"]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def check_preflight_dimensions(cur, expected_dim: int) -> None:
    cur.execute(
        """
        SELECT atttypmod
          FROM pg_attribute
         WHERE attrelid = 'knowledge_chunks'::regclass
           AND attname = 'embedding'
        """
    )
    row = cur.fetchone()
    if not row:
        raise ValidationError("knowledge_chunks table or embedding column not found.")
    if row[0] != expected_dim:
        raise ValidationError(
            f"EMBEDDING_DIMENSIONS ({expected_dim}) does not match database vector dimension ({row[0]})."
        )


def build_import_plan(
    cur,
    chunk_records: List[ChunkRecord],
    provider: str,
    model: str,
    dimensions: int,
) -> ImportPlan:
    """Plan an idempotent upsert for one release without touching older releases."""
    if not chunk_records:
        return ImportPlan()

    for record in chunk_records:
        record.persistence_uuid = persistence_uuid_for(record)
    row_ids = [record.persistence_uuid for record in chunk_records]
    cur.execute(
        "SELECT chunk_id, metadata, is_active FROM knowledge_chunks WHERE chunk_id = ANY(%s::uuid[])",
        (row_ids,),
    )
    existing: Dict[str, Dict[str, Any]] = {}
    for chunk_id, metadata, is_active in cur.fetchall():
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        existing[str(chunk_id)] = {"metadata": metadata or {}, "is_active": is_active}

    expected_identity = f"{provider}:{model}:{dimensions}"
    to_insert: List[ChunkRecord] = []
    to_update: List[ChunkRecord] = []
    to_skip: List[ChunkRecord] = []
    for record in chunk_records:
        current = existing.get(record.persistence_uuid)
        if current is None:
            to_insert.append(record)
            continue
        metadata = current["metadata"]
        unchanged = all(
            (
                metadata.get("content_hash") == record.content_hash,
                metadata.get("chunker_version") == record.chunker_version,
                metadata.get("tokenizer") == record.tokenizer,
                metadata.get("embedding_identity") == expected_identity,
                metadata.get("corpus_release_id") == record.corpus_release_id,
                current["is_active"] == record.is_active,
            )
        )
        (to_skip if unchanged else to_update).append(record)

    release_id = chunk_records[0].corpus_release_id
    cur.execute(
        "SELECT chunk_id FROM knowledge_chunks WHERE metadata->>'corpus_release_id' = %s",
        (release_id,),
    )
    generated = set(row_ids)
    to_retire = [str(row[0]) for row in cur.fetchall() if str(row[0]) not in generated]
    return ImportPlan(
        to_insert=to_insert,
        to_update=to_update,
        to_skip=to_skip,
        to_retire=to_retire,
    )


def upsert_domain(cur, domain_code: str, domain_name: str, owner_role: str) -> str:
    cur.execute(
        """
        INSERT INTO knowledge_domains (domain_code, domain_name, owner_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (domain_code) DO UPDATE SET
            domain_name = EXCLUDED.domain_name,
            owner_name = EXCLUDED.owner_name,
            updated_at = now()
        RETURNING domain_id
        """,
        (domain_code, domain_name, owner_role),
    )
    return str(cur.fetchone()[0])


def persist_batch(
    cur,
    chunks_to_upsert: List[Tuple[ChunkRecord, List[float]]],
    domain_map: Dict[str, str],
) -> None:
    for record, embedding in chunks_to_upsert:
        domain_id = domain_map.get(record.domain)
        if not domain_id:
            raise ValidationError(f"Domain code '{record.domain}' is not configured.")
        row = map_chunk_to_row(record, domain_id, embedding)
        cur.execute(
            """
            INSERT INTO knowledge_chunks (
                chunk_id, domain_id, content, sub_topic, source_id, source_path,
                source_version, approval_status, effective_date, page_numbers,
                tags, metadata, embedding, is_active, created_at, updated_at
            ) VALUES (
                %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s::date,
                %s::jsonb, %s::jsonb, %s::jsonb, %s::vector, %s,
                %s::timestamptz, %s::timestamptz
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                domain_id = EXCLUDED.domain_id,
                content = EXCLUDED.content,
                sub_topic = EXCLUDED.sub_topic,
                source_id = EXCLUDED.source_id,
                source_path = EXCLUDED.source_path,
                source_version = EXCLUDED.source_version,
                approval_status = EXCLUDED.approval_status,
                effective_date = EXCLUDED.effective_date,
                page_numbers = EXCLUDED.page_numbers,
                tags = EXCLUDED.tags,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding,
                is_active = EXCLUDED.is_active,
                retired_at = CASE WHEN EXCLUDED.is_active THEN NULL ELSE knowledge_chunks.retired_at END,
                updated_at = EXCLUDED.updated_at
            """,
            row,
        )


def retire_stale_chunks(cur, chunk_ids: List[str]) -> None:
    if not chunk_ids:
        return
    cur.execute(
        """
        UPDATE knowledge_chunks
           SET is_active = false, retired_at = now(), updated_at = now()
         WHERE chunk_id = ANY(%s::uuid[])
        """,
        (chunk_ids,),
    )


def delete_stale_staged_chunks(cur, release_id: str, chunk_ids: List[str]) -> None:
    """Delete stale rows only from a release that has never been activated."""
    if not chunk_ids:
        return
    cur.execute(
        "SELECT status FROM corpus_releases WHERE release_id = %s FOR UPDATE",
        (release_id,),
    )
    row = cur.fetchone()
    if not row or row[0] not in {"staging", "staged"}:
        raise IngestionError(f"Stale rows can only be removed from a staged release, not {row}.")
    cur.execute(
        "DELETE FROM knowledge_chunks WHERE chunk_id = ANY(%s::uuid[]) AND metadata->>'corpus_release_id' = %s",
        (chunk_ids, release_id),
    )


def register_staging_release(
    cur,
    release_id: str,
    source_count: int,
    chunk_count: int,
    embedding_identity: str,
) -> None:
    cur.execute("SELECT status FROM corpus_releases WHERE release_id = %s FOR UPDATE", (release_id,))
    row = cur.fetchone()
    if row and row[0] in {"verified", "active", "retired"}:
        raise IngestionError(f"Release {release_id} is already {row[0]} and cannot be restaged.")
    cur.execute(
        """
        INSERT INTO corpus_releases (
            release_id, status, expected_source_count, expected_chunk_count,
            embedding_identity, staged_at
        ) VALUES (%s, 'staging', %s, %s, %s, now())
        ON CONFLICT (release_id) DO UPDATE SET
            status = 'staging',
            expected_source_count = EXCLUDED.expected_source_count,
            expected_chunk_count = EXCLUDED.expected_chunk_count,
            embedding_identity = EXCLUDED.embedding_identity,
            staged_at = now(), verified_at = NULL
        """,
        (release_id, source_count, chunk_count, embedding_identity),
    )


def mark_release_staged(cur, release_id: str) -> None:
    cur.execute(
        "UPDATE corpus_releases SET status = 'staged', staged_at = now() WHERE release_id = %s",
        (release_id,),
    )
    if cur.rowcount != 1:
        raise IngestionError(f"Release {release_id} was not registered.")


def activate_release(cur, release_id: str, allowed_source_ids: Set[str]) -> Tuple[int, int]:
    """Activate only a verified complete release, atomically retiring the old one."""
    cur.execute("SELECT status FROM corpus_releases WHERE release_id = %s FOR UPDATE", (release_id,))
    row = cur.fetchone()
    if not row or row[0] != "verified":
        raise IngestionError(f"Release {release_id} must be verified before activation.")

    cur.execute(
        "SELECT DISTINCT source_id FROM knowledge_chunks WHERE metadata->>'corpus_release_id' = %s",
        (release_id,),
    )
    actual_sources = {row[0] for row in cur.fetchall()}
    if actual_sources != allowed_source_ids:
        raise IngestionError(
            f"Release source mismatch; missing={sorted(allowed_source_ids - actual_sources)}, "
            f"unauthorized={sorted(actual_sources - allowed_source_ids)}"
        )

    cur.execute("SELECT release_id FROM corpus_releases WHERE status = 'active' FOR UPDATE")
    active_row = cur.fetchone()
    prior_release_id = active_row[0] if active_row else None
    cur.execute(
        """
        UPDATE knowledge_chunks
           SET is_active = false, retired_at = now(), updated_at = now()
         WHERE is_active = true
           AND COALESCE(metadata->>'corpus_release_id', '') <> %s
        """,
        (release_id,),
    )
    retired = cur.rowcount
    cur.execute(
        """
        UPDATE knowledge_chunks
           SET is_active = true, retired_at = NULL, updated_at = now()
         WHERE metadata->>'corpus_release_id' = %s
        """,
        (release_id,),
    )
    activated = cur.rowcount
    if activated == 0:
        raise IngestionError(f"Release {release_id} contains no chunks.")
    cur.execute(
        "UPDATE corpus_releases SET status = 'retired', retired_at = now() WHERE status = 'active' AND release_id <> %s",
        (release_id,),
    )
    cur.execute(
        """
        UPDATE corpus_releases
           SET status = 'active', activated_at = now(), retired_at = NULL,
               prior_release_id = %s
         WHERE release_id = %s
        """,
        (prior_release_id, release_id),
    )
    return activated, retired


def rollback_release(cur, rollback_target_release_id: str, current_release_id: str) -> Tuple[int, int]:
    """Atomically reactivate an existing complete prior release."""
    cur.execute(
        "SELECT status FROM corpus_releases WHERE release_id = %s FOR UPDATE",
        (rollback_target_release_id,),
    )
    target = cur.fetchone()
    if not target or target[0] not in {"verified", "retired", "active"}:
        raise IngestionError(f"Rollback target {rollback_target_release_id} is not a verified release.")
    cur.execute(
        "SELECT count(*) FROM knowledge_chunks WHERE metadata->>'corpus_release_id' = %s",
        (rollback_target_release_id,),
    )
    if cur.fetchone()[0] == 0:
        raise IngestionError(f"Rollback target {rollback_target_release_id} has no chunks.")

    cur.execute(
        """
        UPDATE knowledge_chunks SET is_active = false, retired_at = now(), updated_at = now()
         WHERE metadata->>'corpus_release_id' = %s AND is_active = true
        """,
        (current_release_id,),
    )
    deactivated = cur.rowcount
    cur.execute(
        """
        UPDATE knowledge_chunks SET is_active = true, retired_at = NULL, updated_at = now()
         WHERE metadata->>'corpus_release_id' = %s
        """,
        (rollback_target_release_id,),
    )
    reactivated = cur.rowcount
    cur.execute(
        "UPDATE corpus_releases SET status = 'retired', retired_at = now() WHERE release_id = %s",
        (current_release_id,),
    )
    cur.execute(
        "UPDATE corpus_releases SET status = 'active', activated_at = now(), retired_at = NULL WHERE release_id = %s",
        (rollback_target_release_id,),
    )
    return reactivated, deactivated
