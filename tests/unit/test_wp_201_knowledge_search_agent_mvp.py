# === TASK:WP-201:START ===
import pytest
from unittest.mock import MagicMock
import apps.api.ai.rag.reranker as reranker_module
from packages.contracts.dto import CitationDTO, SearchCandidateDTO
from apps.api.ai.rag import (
    citation_validation_issues,
    reciprocal_rank_fusion,
    render_citation_markers,
    rerank_candidates,
    map_citations_to_response,
    search_hospital_information,
    supported_response_text,
    check_sufficiency_and_conflicts
)

def test_reciprocal_rank_fusion_logic():
    # 2 vector candidates
    v1 = SearchCandidateDTO("c1", "content 1", 0.9, "bhyt", "sub1", "s1", "p1", "v1")
    v2 = SearchCandidateDTO("c2", "content 2", 0.8, "bhyt", "sub1", "s1", "p1", "v1")

    # 2 lexical candidates (c2 overlaps, c3 is unique)
    l1 = SearchCandidateDTO("c2", "content 2", 0.5, "bhyt", "sub1", "s1", "p1", "v1")
    l2 = SearchCandidateDTO("c3", "content 3", 0.4, "bhyt", "sub1", "s1", "p1", "v1")

    fused = reciprocal_rank_fusion([v1, v2], [l1, l2], k=60)

    # c2 should have higher score than c1 because it appears in both
    assert fused[0].chunk_id == "c2"
    assert fused[1].chunk_id == "c1"
    assert fused[2].chunk_id == "c3"
    assert fused[0].vector_rank == 2
    assert fused[0].lexical_rank == 1
    assert fused[0].fused_rank == 1
    assert fused[1].vector_rank == 1
    assert fused[1].lexical_rank is None
    assert fused[1].fused_rank == 2

def test_reranker_adapter_fallback_on_failure(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "fake")
    c1 = SearchCandidateDTO("c1", "content 1", 0.9, "bhyt", "sub1", "s1", "p1", "v1")

    # Reranking with invalid API response should gracefully fall back to original
    reranked, applied, error = rerank_candidates(
        "query", [c1], api_key="fake", base_url="https://invalid.url", provider="jina"
    )
    assert not applied
    assert error is not None
    assert reranked[0].chunk_id == "c1"


def test_reranker_defaults_to_jina_with_jina_model(monkeypatch):
    monkeypatch.delenv("RERANKER_PROVIDER", raising=False)
    monkeypatch.delenv("RERANKER_JINA_MODEL", raising=False)
    monkeypatch.setenv("JINA_API_KEY", "fake")
    response = MagicMock(status_code=200)
    response.json.return_value = {"results": [{"index": 0, "relevance_score": 0.95}]}
    monkeypatch.setattr(reranker_module.requests, "post", MagicMock(return_value=response))
    candidate = SearchCandidateDTO("c1", "content 1", 0.9, "bhyt", "sub1", "s1", "p1", "v1")

    reranked, applied, error = rerank_candidates("query", [candidate])

    assert applied
    assert error is None
    assert reranked[0].score == 0.95
    assert reranker_module.requests.post.call_args.kwargs["json"]["model"] == reranker_module.JINA_DEFAULT_MODEL


def test_bge_provider_uses_its_provider_specific_model(monkeypatch):
    monkeypatch.setenv("RERANKER_PROVIDER", "bge")
    monkeypatch.setenv("RERANKER_BGE_MODEL", "local/bge-model")
    candidate = SearchCandidateDTO("c1", "content 1", 0.9, "bhyt", "sub1", "s1", "p1", "v1")
    bge = MagicMock(return_value=([candidate], True, None))
    monkeypatch.setattr(reranker_module, "_rerank_with_bge", bge)

    rerank_candidates("query", [candidate])

    assert bge.call_args.args[2] == "local/bge-model"


def test_public_citation_numbers_are_grouped_by_source_id():
    citations = [
        CitationDTO("chunk-1", "source-a", "a.md", "section-1", "", "v1", "claim 1"),
        CitationDTO("chunk-2", "source-a", "a.md", "section-2", "", "v1", "claim 2"),
        CitationDTO("chunk-3", "source-b", "b.md", "section-1", "", "v1", "claim 3"),
    ]

    rendered = render_citation_markers(
        "Thông tin A [[chunk-1]] [[chunk-2]].\nThông tin B [[chunk-2]].\nThông tin C [[chunk-3]].",
        citations,
    )

    assert rendered == "Thông tin A [1].\nThông tin B [1].\nThông tin C [2]."

def test_citation_mapping():
    c1 = SearchCandidateDTO("c1", "Giá dịch vụ khám bệnh là 150.000 VND.", 0.9, "bhyt", "sub1", "s1", "p1", "v1")

    response = "Giá khám bệnh là 150.000 VND. [[c1]]"
    grounded, citations = map_citations_to_response(response, [c1])

    assert grounded
    assert len(citations) == 1
    assert citations[0].chunk_id == "c1"
    assert citations[0].matched_text == "Giá khám bệnh là 150.000 VND."

def test_citation_mapping_rejects_missing_or_unknown_chunk_id():
    c1 = SearchCandidateDTO("c1", "Bệnh viện mở cửa lúc 8:00.", 0.9, "general", "hours", "s1", "p1", "v1")

    assert not map_citations_to_response("Bệnh viện mở cửa lúc 8:00.", [c1])[0]
    assert not map_citations_to_response("Bệnh viện mở cửa lúc 8:00. [[fake]]", [c1])[0]
    assert citation_validation_issues("Bệnh viện mở cửa lúc 8:00.", [c1])[0].startswith("missing_citation")
    assert citation_validation_issues("Bệnh viện mở cửa lúc 8:00. [[fake]]", [c1]) == ["unknown_chunk_id: fake"]

def test_citation_mapping_rejects_unsupported_number():
    c1 = SearchCandidateDTO("c1", "Bệnh viện mở cửa lúc 8:00.", 0.9, "general", "hours", "s1", "p1", "v1")

    grounded, _ = map_citations_to_response("Bệnh viện mở cửa lúc 9:00. [[c1]]", [c1])

    assert not grounded
    assert citation_validation_issues("Bệnh viện mở cửa lúc 9:00. [[c1]]", [c1]) == ["unsupported_number: 9:00"]


def test_uncited_section_label_is_not_treated_as_factual_claim():
    c1 = SearchCandidateDTO("c1", "Người bệnh chuẩn bị CCCD trước khi đến.", 0.9, "general", "procedure", "s1", "p1", "v1")
    response = "1) Chuẩn bị trước khi đến bệnh viện\n- Người bệnh chuẩn bị CCCD trước khi đến. [[c1]]"

    grounded, citations = map_citations_to_response(response, [c1])

    assert grounded
    assert len(citations) == 1


def test_unsupported_claim_is_dropped_without_losing_supported_claim():
    c1 = SearchCandidateDTO("c1", "Bệnh viện mở cửa lúc 8:00.", 0.9, "general", "hours", "s1", "p1", "v1")
    response = (
        "Thông tin giờ làm việc:\n"
        "- Bệnh viện mở cửa lúc 8:00. [[c1]]\n"
        "- Bệnh viện đóng cửa lúc 21:00. [[c1]]"
    )

    filtered = supported_response_text(response, [c1])

    assert "8:00" in filtered
    assert "21:00" not in filtered

def test_sufficiency_conflict_detection():
    c1 = SearchCandidateDTO("c1", "Giá dịch vụ: 150.000 VND.", 0.9, "bhyt", "khám bệnh", "s1", "p1", "v1")
    c2 = SearchCandidateDTO("c2", "Giá dịch vụ: 200.000 VND.", 0.8, "bhyt", "khám bệnh", "s1", "p1", "v1")

    # Two candidates in the same subtopic but different prices -> conflict
    sufficient, reason = check_sufficiency_and_conflicts([c1, c2])
    assert not sufficient
    assert "Conflict detected" in reason

    # No conflict when price matches
    c3 = SearchCandidateDTO("c3", "Giá dịch vụ: 150.000 VND.", 0.8, "bhyt", "khám bệnh", "s1", "p1", "v1")
    sufficient, reason = check_sufficiency_and_conflicts([c1, c3])
    assert sufficient


def test_sufficiency_does_not_treat_reference_numbers_as_prices():
    c1 = SearchCandidateDTO("c1", "Tham khảo mục 463 của quy trình.", 0.9, "bhyt", "tiếp đón", "s1", "p1", "v1")
    c2 = SearchCandidateDTO("c2", "Tham khảo mục 477 của quy trình.", 0.8, "bhyt", "tiếp đón", "s1", "p1", "v1")

    sufficient, reason = check_sufficiency_and_conflicts([c1, c2])

    assert sufficient
    assert reason is None
# === TASK:WP-201:END ===
