# === TASK:WP-102:START ===
import time
from typing import List, Tuple, Optional

from packages.contracts.dto import SearchCandidateDTO, DegradationMetadataDTO
from apps.api.core.trace_logging import trace_event
from .vector_search import vector_search
from .lexical_search import lexical_search


def hybrid_search(
    cur,
    query_text: str,
    query_vector: Optional[List[float]],
    limit: int = 5,
    trace_id: Optional[str] = None,
) -> Tuple[List[SearchCandidateDTO], List[SearchCandidateDTO], DegradationMetadataDTO]:
    """Execute vector and lexical searches independently, handling single-lane degradation."""
    vector_candidates = []
    lexical_candidates = []

    provider_failure = False
    model_failure = False
    reasons = []

    # 1. Execute vector lane
    if query_vector is not None:
        vector_started = time.monotonic()
        trace_event("rag.vector.start", trace_id=trace_id, limit=limit)
        try:
            vector_candidates = vector_search(cur, query_vector, limit)
            trace_event(
                "rag.vector.complete",
                trace_id=trace_id,
                started_at=vector_started,
                candidate_count=len(vector_candidates),
            )
        except Exception as exc:
            provider_failure = True
            reasons.append(f"Vector search failed: {exc}")
            trace_event(
                "rag.vector.error",
                trace_id=trace_id,
                started_at=vector_started,
                error_type=type(exc).__name__,
            )
    else:
        provider_failure = True
        reasons.append("No query vector provided")

    # 2. Execute lexical lane
    lexical_started = time.monotonic()
    trace_event("rag.lexical.start", trace_id=trace_id, limit=limit)
    try:
        lexical_candidates = lexical_search(cur, query_text, limit)
        trace_event(
            "rag.lexical.complete",
            trace_id=trace_id,
            started_at=lexical_started,
            candidate_count=len(lexical_candidates),
        )
    except Exception as exc:
        model_failure = True
        reasons.append(f"Lexical search failed: {exc}")
        trace_event(
            "rag.lexical.error",
            trace_id=trace_id,
            started_at=lexical_started,
            error_type=type(exc).__name__,
        )

    # 3. If both failed, raise a stable generic error
    if provider_failure and model_failure:
        trace_event("rag.hybrid.fallback", trace_id=trace_id, reason="both_lanes_failed")
        raise RuntimeError("RAG search tool is currently unavailable due to database or provider errors.")

    degradation = DegradationMetadataDTO(
        provider_failure=provider_failure,
        model_failure=model_failure,
        reranker_failure=False,
        fallback_active=provider_failure or model_failure,
        reason="; ".join(reasons) if reasons else None
    )

    return vector_candidates, lexical_candidates, degradation
# === TASK:WP-102:END ===
