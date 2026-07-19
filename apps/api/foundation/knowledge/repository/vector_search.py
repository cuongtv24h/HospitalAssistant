# === TASK:WP-102:START ===
from typing import List
from packages.contracts.dto import SearchCandidateDTO

def vector_search(cur, query_vector: List[float], limit: int = 5) -> List[SearchCandidateDTO]:
    """Perform cosine similarity vector search over knowledge chunks."""
    query = """
        SELECT 
            kc.chunk_id,
            kc.content,
            kc.sub_topic,
            kc.source_id,
            kc.source_path,
            kc.source_version,
            kc.metadata,
            kd.domain_code,
            (1 - (kc.embedding <=> %s::vector)) as score
        FROM knowledge_chunks kc
        JOIN knowledge_domains kd ON kc.domain_id = kd.domain_id
        WHERE kc.is_active = true
          AND kc.approval_status IN ('approved_for_pilot', 'approved')
          AND EXISTS (
              SELECT 1 FROM corpus_releases cr
               WHERE cr.release_id = kc.metadata->>'corpus_release_id'
                 AND cr.status = 'active'
          )
          AND (kc.effective_date IS NULL OR kc.effective_date <= CURRENT_DATE)
          AND COALESCE((kc.metadata->>'answerable')::boolean, true) IS TRUE
          AND COALESCE((kc.metadata->>'extraction_incomplete')::boolean, false) IS FALSE
        ORDER BY kc.embedding <=> %s::vector
        LIMIT %s
    """
    cur.execute(query, (query_vector, query_vector, limit))
    rows = cur.fetchall()
    
    candidates = []
    for row in rows:
        chunk_uuid = str(row[0])
        content = row[1]
        sub_topic = row[2] or ""
        source_id = row[3]
        source_path = row[4]
        source_version = row[5]
        meta = row[6] or {}
        if isinstance(meta, str):
            import json
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        domain_code = row[7]
        score = float(row[8])
        
        external_id = meta.get("external_chunk_id") or chunk_uuid
        
        candidates.append(SearchCandidateDTO(
            chunk_id=external_id,
            content=content,
            score=score,
            domain=domain_code,
            sub_topic=meta.get("section_path") or sub_topic,
            source_id=meta.get("source_id") or source_id,
            source_path=meta.get("ingestion_path") or source_path,
            version=meta.get("version") or source_version,
            source_kind=meta.get("source_kind", "web"),
            title=meta.get("title") or source_id,
            display_name=meta.get("display_name") or meta.get("title") or source_id,
            source_url=meta.get("source_url"),
            publisher=meta.get("publisher", "Bệnh viện Tim Hà Nội"),
            section_path=meta.get("section_path", ""),
            crawled_at=meta.get("crawled_at"),
            effective_date=meta.get("effective_date"),
            corpus_release_id=meta.get("corpus_release_id", ""),
            answerable=meta.get("answerable", True),
        ))
    return candidates

# === TASK:WP-102:END ===
