# === TASK:WP-102:START ===
import re
import unicodedata
from typing import List

from packages.contracts.dto import SearchCandidateDTO


_VIETNAMESE_STOP_WORDS = {
    "ai", "bằng", "bị", "các", "cái", "cho", "có", "của", "được",
    "gì", "hay", "khi", "là", "một", "những", "ở", "ra", "sao",
    "thế", "thì", "trong", "tôi", "và", "về", "với",
}


def build_sparse_tsquery(query_text: str) -> str:
    """Build a tolerant OR tsquery for Vietnamese keyword retrieval.

    PostgreSQL ``plainto_tsquery`` joins every token with AND. That is brittle
    for natural Vietnamese questions because one low-value token can prevent a
    match. This builder keeps meaningful tokens, expands the common BHYT
    abbreviation, and joins terms with OR so ranking can reward partial matches.
    """
    normalized = unicodedata.normalize("NFC", query_text).lower()
    tokens = re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)
    meaningful = [token for token in tokens if token not in _VIETNAMESE_STOP_WORDS]

    if "bhyt" in meaningful or {"bảo", "hiểm", "y", "tế"}.issubset(meaningful):
        meaningful.extend(["bhyt", "bảo", "hiểm", "y", "tế"])

    unique_tokens = list(dict.fromkeys(meaningful))
    return " | ".join(unique_tokens)


def lexical_search(cur, query_text: str, limit: int = 5) -> List[SearchCandidateDTO]:
    """Perform tolerant sparse search over approved knowledge chunks."""
    sparse_query = build_sparse_tsquery(query_text)
    if not sparse_query:
        return []

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
            ts_rank_cd(kc.search_document, to_tsquery('simple', %s), 32) as score
        FROM knowledge_chunks kc
        JOIN knowledge_domains kd ON kc.domain_id = kd.domain_id
        WHERE kc.is_active = true
          AND kc.approval_status IN ('approved_for_pilot', 'approved')
          AND (kc.effective_date IS NULL OR kc.effective_date <= CURRENT_DATE)
          AND kc.search_document @@ to_tsquery('simple', %s)
        ORDER BY score DESC, kc.chunk_id
        LIMIT %s
    """
    cur.execute(query, (sparse_query, sparse_query, limit))
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
        domain_code = row[7]
        score = float(row[8])

        external_id = meta.get("external_chunk_id", chunk_uuid)

        candidates.append(SearchCandidateDTO(
            chunk_id=external_id,
            content=content,
            score=score,
            domain=domain_code,
            sub_topic=sub_topic,
            source_id=source_id,
            source_path=source_path,
            version=source_version
        ))
    return candidates
# === TASK:WP-102:END ===
