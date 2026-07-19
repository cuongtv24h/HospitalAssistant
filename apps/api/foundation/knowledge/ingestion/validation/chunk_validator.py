# === TASK:WP-008:START ===
from typing import List
from ..models import ChunkRecord

def validate_chunk(rec: ChunkRecord, hard_max_tokens: int = 700) -> List[str]:
    errors = []
    if not rec.chunk_id or not rec.external_chunk_id:
        errors.append("Chunk missing chunk_id or external_chunk_id")
    if not rec.content or not rec.content.strip():
        errors.append(f"Chunk {rec.chunk_id} has empty content")
    if not rec.source_id:
        errors.append(f"Chunk {rec.chunk_id} missing source_id")
    if not rec.title or not rec.display_name:
        errors.append(f"Chunk {rec.chunk_id} missing title or display_name")
    if rec.source_kind == "web" and not rec.source_url:
        errors.append(f"Chunk {rec.chunk_id} web source missing source_url")
    if rec.source_kind == "document" and rec.source_url is not None:
        errors.append(f"Chunk {rec.chunk_id} document source must have null source_url")
    if rec.token_count > hard_max_tokens:
        errors.append(f"Chunk {rec.chunk_id} exceeds hard max token limit: {rec.token_count} > {hard_max_tokens}")
    if not rec.source_content_hash or not rec.content_hash:
        errors.append(f"Chunk {rec.chunk_id} missing content hash metadata")
    if not rec.chunker_version or not rec.tokenizer or not rec.corpus_release_id:
        errors.append(f"Chunk {rec.chunk_id} missing chunker/tokenizer/release identity")
    if rec.extraction_incomplete and rec.answerable:
        errors.append(f"Chunk {rec.chunk_id} is extraction_incomplete but marked answerable")

    return errors
# === TASK:WP-008:END ===
