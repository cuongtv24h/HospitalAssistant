import pytest
from pathlib import Path
from apps.api.foundation.knowledge.ingestion.sources.registry import (
    load_authoritative_registry,
    validate_authoritative_registry,
)

def test_authoritative_source_registry_valid():
    registry = load_authoritative_registry()
    errors = validate_authoritative_registry(registry)
    assert errors == [], f"Validation errors found in authoritative registry: {errors}"
    assert len(registry["sources"]) == 25

def test_authoritative_source_registry_invalid_cases(tmp_path):
    # Test duplicate ID
    reg = {
        "sources": [
            {"source_id": "SRC-1", "source_kind": "web", "source_url": "https://a.com", "ingestion_path": "a.md"},
            {"source_id": "SRC-1", "source_kind": "web", "source_url": "https://a.com", "ingestion_path": "a.md"},
        ]
    }
    errors = validate_authoritative_registry(reg, root_dir=tmp_path)
    assert any("must contain exactly 25 sources" in e for e in errors)
    assert any("Duplicate source_id" in e for e in errors)

    # Test mock source
    reg = {"sources": [{"source_id": "SRC-MOCK-001", "is_mock": True}] * 25}
    errors = validate_authoritative_registry(reg, root_dir=tmp_path)
    assert any("Mock source SRC-MOCK-001 not allowed" in e for e in errors)

    # Test missing PDF display name
    reg_doc = {
        "sources": [
            {
                "source_id": f"SRC-DOC-{i}",
                "source_kind": "document",
                "source_url": None,
                "display_name": "NoPdfExtension",
                "ingestion_path": "file.md"
            }
            for i in range(25)
        ]
    }
    errors = validate_authoritative_registry(reg_doc, root_dir=tmp_path)
    assert any("missing valid PDF display_name" in e for e in errors)
