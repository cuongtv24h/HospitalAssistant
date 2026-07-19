# MVP Seed Data & Knowledge Corpus Registry

> **IMPORTANT**: The authoritative knowledge RAG corpus is strictly defined by `authoritative-source-registry.json` (exactly 25 sources: 22 website documents + 3 core local documents).

The following files are **not** authoritative inputs for the RAG ingestion pipeline:
- `knowledge-base.json` (contains legacy predefined and mock chunks)
- `source-registry.json` (legacy registry)
- Generated `processed/*.jsonl`
- Non-selected BHYT documents under `docs/knowledge/bhyt/` (except `bieugia_bhyt.md`)
- Any `SRC-MOCK-*` sources
