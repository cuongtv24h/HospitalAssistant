from dataclasses import replace

from apps.api.ai.rag.reranker import _with_score
from apps.api.ai.rag.rrf import reciprocal_rank_fusion
from apps.api.foundation.knowledge.ingestion.persistence.mapper import persistence_uuid_for
from apps.api.foundation.knowledge.ingestion.persistence.postgres import psycopg_connection_url, redact_connection_url
from apps.api.foundation.operational_repository import OperationalRepository
from packages.contracts.dto import SearchCandidateDTO
from scripts.ingest_authoritative_knowledge import _prepare_corpus


def test_authoritative_corpus_is_exact_clean_and_staged_inactive():
    registry, sources, chunks, errors = _prepare_corpus("release-test")

    assert errors == []
    assert len(registry["sources"]) == 25
    assert len([source for source in sources if source.source_kind == "web"]) == 22
    assert len([source for source in sources if source.source_kind == "document"]) == 3
    assert {chunk.source_id for chunk in chunks} == {source["source_id"] for source in registry["sources"]}
    assert all(not chunk.content.startswith("---") for chunk in chunks)
    assert all(chunk.approval_status == "approved" for chunk in chunks)
    assert all(chunk.is_active is False for chunk in chunks)
    assert all(chunk.embedding_text.startswith("Tài liệu:") for chunk in chunks)
    assert all(chunk.embedding_identity == "jina:jina-embeddings-v5-text-small:1024" for chunk in chunks)
    assert all(chunk.domain in {
        "thong_tin_benh_vien", "dat_lich", "quy_trinh", "bhyt",
        "gia_dich_vu", "gio_lam_viec", "bac_si_khoa",
    } for chunk in chunks)


def test_persistence_identity_is_idempotent_within_release_and_scoped_between_releases():
    _, _, chunks, _ = _prepare_corpus("release-a")
    first = chunks[0]
    same = replace(first)
    other_release = replace(first, corpus_release_id="release-b")

    assert persistence_uuid_for(first) == persistence_uuid_for(same)
    assert persistence_uuid_for(first) != persistence_uuid_for(other_release)


def test_ranking_layers_preserve_authoritative_provenance():
    candidate = SearchCandidateDTO(
        chunk_id="chunk-1",
        content="Bằng chứng",
        score=0.4,
        domain="bhyt",
        sub_topic="Mức hưởng",
        source_id="HHH-INS-001",
        source_path="internal.md",
        version="1.0",
        source_kind="web",
        title="Thông báo BHYT",
        display_name="Thông báo BHYT",
        source_url="https://benhvientimhanoi.vn/bhyt",
        publisher="Bệnh viện Tim Hà Nội",
        section_path="BHYT > Mức hưởng",
        crawled_at="2026-07-18T00:00:00Z",
        corpus_release_id="release-a",
        answerable=True,
    )

    fused = reciprocal_rank_fusion([candidate], [], k=60)[0]
    reranked = _with_score(fused, 0.99)
    assert reranked.source_url == candidate.source_url
    assert reranked.display_name == candidate.display_name
    assert reranked.section_path == candidate.section_path
    assert reranked.corpus_release_id == candidate.corpus_release_id


def test_supabase_pooler_url_is_libpq_safe_and_logs_are_redacted():
    url = "postgresql://operator:secret@pooler.example:6543/postgres?pgbouncer=true&sslmode=require"
    assert psycopg_connection_url(url) == (
        "postgresql://operator:secret@pooler.example:6543/postgres?sslmode=require"
    )
    redacted = redact_connection_url(url)
    assert "secret" not in redacted
    assert "operator" not in redacted
    assert redacted == "postgresql://***@pooler.example:6543/postgres"


def test_operational_repository_accepts_supabase_pooler_url():
    repository = OperationalRepository(
        "postgresql://operator:secret@pooler.example:6543/postgres?pgbouncer=true&sslmode=require"
    )

    assert repository._database_url == (
        "postgresql://operator:secret@pooler.example:6543/postgres?sslmode=require"
    )
