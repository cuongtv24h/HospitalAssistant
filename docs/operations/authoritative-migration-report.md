# Authoritative knowledge migration report

- Migration date: 2026-07-19
- Database target: Supabase staging project (credentials redacted)
- Accepted release: `hhh-authoritative-2026-07-19-v1`
- Final status: `active`
- Active release count: 1
- Source count: 25 (22 website sources, 3 local documents)
- Chunk count: 167
- Answerable chunks: 149
- Extraction-incomplete/non-answerable chunks: 18
- Mock chunks: 0
- Embedding identity: `jina:jina-embeddings-v5-text-small:1024`
- Vector dimensions: 1024
- Jina reranker: verified successfully with a 15-second timeout
- Golden retrieval: passed for appointment, procedure, BHYT, pricing,
  doctors/departments, and general hospital information
- Schedule safety gate: passed; incomplete source `HHH-SCH-001` was not
  returned as factual evidence
- Website citation shape: canonical HTTP(S) URL verified
- Local citation shape: plain PDF display name without URL verified
- Rollback rehearsal release: `hhh-authoritative-rollback-rehearsal`
- Rollback rehearsal: accepted → rehearsal → accepted, 167 chunks switched
  transactionally in each direction; rehearsal release is now retired
- Final verification report:
  `migration-reports/authoritative-hhh-authoritative-2026-07-19-v1-final.json`

The BHYT source contains the document heading `Bảng giá BHYT — Tổng hợp` but
does not provide a distinct original PDF filename. The approved registry label
therefore remains `Biểu giá BHYT.pdf`. Runtime cross-database automatic fallback
is not implemented; deployment database selection remains environment-only.
