# === TASK:WP-201:START ===
import os
import re
import time
from typing import List, Tuple, Optional
from packages.contracts.dto import SearchCandidateDTO, SearchResultDTO, DegradationMetadataDTO
from apps.api.foundation.knowledge.repository import hybrid_search
from .rrf import reciprocal_rank_fusion
from .reranker import rerank_candidates
from apps.api.core.trace_logging import trace_event

def check_sufficiency_and_conflicts(candidates: List[SearchCandidateDTO]) -> Tuple[bool, Optional[str]]:
    """Determine if candidates are sufficient and free from contradictory facts."""
    if not candidates:
        return False, "No candidates found"

    # Detect only explicit monetary prices. Generic three-digit values can be
    # page/reference/decision numbers and are not evidence of a price conflict.
    prices = {}
    for c in candidates:
        if c.sub_topic:
            price_match = re.findall(
                r"\b\d{1,3}(?:[. ,]\d{3})+(?=\s*(?:đồng|vnđ|vnd)\b)",
                c.content,
                flags=re.IGNORECASE,
            )
            if price_match:
                price_val = re.sub(r"\D", "", price_match[0])
                if c.sub_topic in prices and prices[c.sub_topic] != price_val:
                    return False, f"Conflict detected in topic '{c.sub_topic}': {prices[c.sub_topic]} vs {price_val}"
                prices[c.sub_topic] = price_val

    return True, None


def search_hospital_information(
    cur,
    query: str,
    embedder,
    reranker_api_key: Optional[str] = None,
    reranker_model: Optional[str] = None,
    reranker_base_url: str = "https://api.jina.ai/v1/rerank",
    reranker_timeout: float = 5.0,
    top_n: int = 5,
    rrf_k: int = 60,
    trace_id: Optional[str] = None,
) -> SearchResultDTO:
    """The evidence-returning search tool over query embedding, hybrid retrieval, RRF, and Jina Reranking."""
    # 1. Embed query (safe preflight validation inside embedder)
    total_started = time.monotonic()
    embedding_started = time.monotonic()
    trace_event("rag.embedding.start", trace_id=trace_id)
    try:
        query_vector = embedder.embed_query(query)
        trace_event("rag.embedding.complete", trace_id=trace_id, started_at=embedding_started, dimensions=len(query_vector or []))
    except Exception as exc:
        # Fall back to lexical search
        query_vector = None
        cause = exc.__cause__
        status = None
        if cause is not None and getattr(cause, "response", None) is not None:
            status = getattr(cause.response, "status_code", None)
        trace_event(
            "rag.embedding.error",
            trace_id=trace_id,
            started_at=embedding_started,
            error_type=type(exc).__name__,
            cause_type=type(cause).__name__ if cause is not None else None,
            http_status=status,
            fallback="sparse_only",
        )

    # 2. Query hybrid lanes
    hybrid_started = time.monotonic()
    vector_cands, lexical_cands, degradation = hybrid_search(cur, query, query_vector, limit=20, trace_id=trace_id)
    trace_event("rag.hybrid.complete", trace_id=trace_id, started_at=hybrid_started, vector_count=len(vector_cands), lexical_count=len(lexical_cands), degraded=degradation.fallback_active, degradation_reason=degradation.reason)

    # 3. Fuse ranks with RRF
    rrf_started = time.monotonic()
    fused_cands = reciprocal_rank_fusion(vector_cands, lexical_cands, k=rrf_k)
    trace_event("rag.rrf.complete", trace_id=trace_id, started_at=rrf_started, input_vector_count=len(vector_cands), input_lexical_count=len(lexical_cands), fused_count=len(fused_cands), rrf_k=rrf_k)

    # 4. Jina Reranking
    reranker_applied = False
    rerank_error = None
    final_candidates = fused_cands[:top_n]

    reranker_enabled = os.environ.get("RERANKER_ENABLED", "true").lower() == "true"
    if fused_cands and reranker_enabled:
        rerank_started = time.monotonic()
        trace_event("rag.rerank.start", trace_id=trace_id, provider=os.environ.get("RERANKER_PROVIDER", "jina"), candidate_count=min(len(fused_cands), 20))
        reranked, reranker_applied, rerank_error = rerank_candidates(
            query=query,
            candidates=fused_cands[:20],
            api_key=reranker_api_key,
            model=reranker_model,
            base_url=reranker_base_url,
            timeout=reranker_timeout,
            top_n=top_n,
            provider=os.environ.get("RERANKER_PROVIDER", "jina"),
            trace_id=trace_id,
        )
        if reranker_applied:
            final_candidates = reranked
        trace_event("rag.rerank.complete", trace_id=trace_id, started_at=rerank_started, applied=reranker_applied, output_count=len(reranked), fallback_reason=rerank_error)
    elif not reranker_enabled:
        trace_event("rag.rerank.skipped", trace_id=trace_id, reason="disabled")
    elif not fused_cands:
        trace_event("rag.rerank.skipped", trace_id=trace_id, reason="no_candidates")

    # 5. Sufficiency and conflict checks
    sufficient, conflict_reason = check_sufficiency_and_conflicts(final_candidates)
    trace_event("rag.sufficiency.complete", trace_id=trace_id, sufficient=sufficient, candidate_count=len(final_candidates), conflict_reason=conflict_reason)

    metadata = {
        "provider_failure": degradation.provider_failure,
        "model_failure": degradation.model_failure,
        "reranker_applied": reranker_applied,
        "rerank_error": rerank_error,
        "conflict_reason": conflict_reason,
        "vector_candidate_count": len(vector_cands),
        "lexical_candidate_count": len(lexical_cands)
    }

    result = SearchResultDTO(
        sufficient=sufficient,
        candidates=final_candidates,
        metadata=metadata
    )
    trace_event("rag.search.complete", trace_id=trace_id, started_at=total_started, sufficient=sufficient, candidate_count=len(final_candidates))
    return result
# === TASK:WP-201:END ===
