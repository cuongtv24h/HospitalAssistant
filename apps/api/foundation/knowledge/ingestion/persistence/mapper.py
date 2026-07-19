# === TASK:WP-008:START ===
import json
import datetime
import uuid
from typing import Tuple, List, Any
from ..models import ChunkRecord


def persistence_uuid_for(record: ChunkRecord) -> str:
    """Return a stable row UUID scoped to a corpus release.

    External chunk IDs intentionally remain stable across releases. Database
    row IDs include the release so staging a replacement cannot overwrite the
    prior release that is needed for rollback.
    """
    external_id = record.external_chunk_id or record.chunk_id
    identity = f"{record.corpus_release_id}|{external_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))

def map_chunk_to_row(
    record: ChunkRecord,
    domain_id: str,
    embedding: List[float]
) -> Tuple[Any, ...]:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    page_numbers = json.dumps([record.source_page] if record.source_page else [])
    tags = json.dumps(record.tags)
    
    chunk_uuid = persistence_uuid_for(record)

    record.persistence_uuid = chunk_uuid

    emb_identity = record.embedding_identity or f"{record.embedding_provider}:{record.embedding_model}:{record.embedding_dimensions}"
    metadata = json.dumps({
        "external_chunk_id": record.external_chunk_id or record.chunk_id,
        "source_id": record.source_id,
        "source_kind": record.source_kind,
        "title": record.title,
        "display_name": record.display_name,
        "source_url": record.source_url,
        "ingestion_path": record.ingestion_path or record.source_path,
        "publisher": record.publisher,
        "topic": record.topic,
        "section_path": record.section_path,
        "version": record.version,
        "effective_date": record.effective_date,
        "crawled_at": record.crawled_at,
        "source_content_hash": record.source_content_hash,
        "content_hash": record.content_hash,
        "chunker_version": record.chunker_version,
        "tokenizer": record.tokenizer,
        "token_count": record.token_count,
        "split_reason": record.split_reason,
        "quality_flags": record.quality_flags,
        "extraction_incomplete": record.extraction_incomplete,
        "answerable": record.answerable,
        "embedding_identity": emb_identity,
        "corpus_release_id": record.corpus_release_id,
    }, ensure_ascii=False)
    
    embedding_json = json.dumps(embedding)
    
    return (
        chunk_uuid,
        domain_id,
        record.content,
        record.sub_topic or record.section_path,
        record.source_id,
        record.ingestion_path or record.source_path,
        record.version,
        record.approval_status,
        record.effective_date or None,
        page_numbers,
        tags,
        metadata,
        embedding_json,
        record.is_active,
        now,
        now,
    )
# === TASK:WP-008:END ===
