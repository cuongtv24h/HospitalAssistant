import pytest
from packages.contracts.dto import SearchCandidateDTO, CitationDTO
from apps.api.ai.rag.citations import map_citations_to_response, render_citation_markers

def test_same_source_multi_chunk_citations_deduplicated():
    candidate_1 = SearchCandidateDTO(
        chunk_id="HHH-INS-001:abcd1234efgh5678",
        content="Nội dung BHYT phần 1: Mức hưởng BHYT ngoại trú là 100%",
        score=0.9,
        domain="insurance",
        sub_topic="BHYT",
        source_id="HHH-INS-001",
        source_path="hospital_assistant/data/knowledge/section_1/documents/hhh-ins-001.md",
        version="1.0",
        source_kind="web",
        title="Thông báo BHYT",
        display_name="Thông báo BHYT",
        source_url="https://benhvientimhanoi.vn/vi/chi-tiet/pho-bien-kien-thuc/thong-bao-bhyt",
    )

    candidate_2 = SearchCandidateDTO(
        chunk_id="HHH-INS-001:8765hgfe4321dcba",
        content="Nội dung BHYT phần 2",
        score=0.85,
        domain="insurance",
        sub_topic="BHYT",
        source_id="HHH-INS-001",
        source_path="hospital_assistant/data/knowledge/section_1/documents/hhh-ins-001.md",
        version="1.0",
        source_kind="web",
        title="Thông báo BHYT",
        display_name="Thông báo BHYT",
        source_url="https://benhvientimhanoi.vn/vi/chi-tiet/pho-bien-kien-thuc/thong-bao-bhyt",
    )

    candidates = [candidate_1, candidate_2]
    text = "Mức hưởng BHYT ngoại trú là 100% [[HHH-INS-001:abcd1234efgh5678]] và quy định chuyển tuyến [[HHH-INS-001:8765hgfe4321dcba]]."
    
    grounded, citations = map_citations_to_response(text, candidates)
    assert grounded is True
    assert len(citations) == 2

    # Verify render_citation_markers uses 1 citation number for same source_id
    rendered = render_citation_markers(text, citations)
    assert rendered == "Mức hưởng BHYT ngoại trú là 100% [1] và quy định chuyển tuyến [1]."

def test_unknown_chunk_marker_rejected():
    candidate = SearchCandidateDTO(
        chunk_id="HHH-INS-001:abcd1234efgh5678",
        content="Nội dung BHYT",
        score=0.9,
        domain="insurance",
        sub_topic="BHYT",
        source_id="HHH-INS-001",
        source_path="hospital_assistant/data/knowledge/section_1/documents/hhh-ins-001.md",
        version="1.0",
    )
    text = "Nội dung này có trích dẫn lạ [[UNKNOWN_CHUNK_ID]]."
    grounded, citations = map_citations_to_response(text, [candidate])
    assert grounded is False
    assert citations == []

def test_multi_source_ordering():
    c1 = SearchCandidateDTO(
        chunk_id="SRC-1:c1", content="Text 1", score=0.9, domain="gen", sub_topic="", source_id="SRC-1", source_path="1.md", version="1"
    )
    c2 = SearchCandidateDTO(
        chunk_id="SRC-2:c2", content="Text 2", score=0.8, domain="gen", sub_topic="", source_id="SRC-2", source_path="2.md", version="1"
    )
    text = "Nội dung 1 [[SRC-1:c1]]. Nội dung 2 [[SRC-2:c2]]."
    grounded, citations = map_citations_to_response(text, [c1, c2])
    assert grounded is True
    rendered = render_citation_markers(text, citations)
    assert rendered == "Nội dung 1 [1]. Nội dung 2 [2]."
