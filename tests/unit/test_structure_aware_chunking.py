import pytest
from pathlib import Path
from apps.api.foundation.knowledge.ingestion.models import SourceRecord
from apps.api.foundation.knowledge.ingestion.sources.provenance import normalize_source_record, load_manifest
from apps.api.foundation.knowledge.ingestion.chunking.structure_chunker import chunk_source_record

def test_structure_aware_chunking_web_document():
    root_dir = Path(".")
    entry = {
        "source_id": "HHH-GEN-001",
        "source_kind": "web",
        "title": "Trang chủ - Bệnh viện Tim Hà Nội",
        "display_name": "Trang chủ - Bệnh viện Tim Hà Nội",
        "source_url": "https://benhvientimhanoi.vn/",
        "publisher": "Bệnh viện Tim Hà Nội",
        "topic": "general",
        "version": "1.0",
        "ingestion_path": "hospital_assistant/data/knowledge/section_1/documents/hhh-gen-001.md",
        "extraction_incomplete": False
    }
    source_rec, warnings = normalize_source_record(entry, root_dir=root_dir)
    assert warnings == []
    assert source_rec.source_kind == "web"
    
    full_path = root_dir / entry["ingestion_path"]
    body = full_path.read_text(encoding="utf-8")
    
    chunks = chunk_source_record(source_rec, body, release_id="test-rel-1")
    assert len(chunks) > 0
    
    for c in chunks:
        assert c.source_id == "HHH-GEN-001"
        assert c.source_kind == "web"
        assert c.source_url == "https://benhvientimhanoi.vn/"
        assert c.display_name == "Trang chủ - Bệnh viện Tim Hà Nội"
        assert c.embedding_text.startswith("Tài liệu: Trang chủ - Bệnh viện Tim Hà Nội")
        assert c.corpus_release_id == "test-rel-1"
        assert c.answerable is True

def test_structure_aware_chunking_local_document():
    root_dir = Path(".")
    entry = {
        "source_id": "SRC-PROCESS-001",
        "source_kind": "document",
        "title": "Quy trình đón tiếp bệnh nhân",
        "display_name": "Quy trình đón tiếp bệnh nhân.pdf",
        "source_url": None,
        "publisher": "Bệnh viện Tim Hà Nội",
        "topic": "procedure",
        "version": "1.0",
        "ingestion_path": "docs/knowledge/quy-trinh-don-tiep-benh-nhan_chuan-hoa-doi-chieu-nguon.md",
        "extraction_incomplete": False
    }
    source_rec, warnings = normalize_source_record(entry, root_dir=root_dir)
    assert source_rec.source_kind == "document"
    assert source_rec.display_name == "Quy trình đón tiếp bệnh nhân.pdf"
    assert source_rec.source_url is None
    
    full_path = root_dir / entry["ingestion_path"]
    body = full_path.read_text(encoding="utf-8")
    
    chunks = chunk_source_record(source_rec, body, release_id="test-rel-1")
    assert len(chunks) > 0
    for c in chunks:
        assert c.source_id == "SRC-PROCESS-001"
        assert c.source_kind == "document"
        assert c.source_url is None
        assert c.display_name == "Quy trình đón tiếp bệnh nhân.pdf"
