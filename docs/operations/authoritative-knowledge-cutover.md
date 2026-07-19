# Authoritative knowledge cutover

This runbook stages exactly 22 Hanoi Heart Hospital web documents and three
approved local documents. It never performs automatic cross-database fallback.
Changing the runtime database remains an explicit deployment configuration
change after acceptance.

## Prerequisites

- Rotate the Supabase password that was previously disclosed.
- Keep `DATABASE_URL` and `JINA_API_KEY` in a local, untracked shell or secret
  manager. Never paste either value into Git, reports, or command history.
- Percent-encode reserved characters in the database password. The scripts
  accept Supabase pooler URLs containing `pgbouncer=true` and remove that
  client-only option before passing the URL to psycopg/libpq.
- The target database must already contain the base `knowledge_domains` and
  `knowledge_chunks` schema with `embedding vector(1024)`.
- Use the project virtual environment and run commands from the repository root.

```bash
source .venv/bin/activate
set -a
source .env
set +a

export AUTHORITATIVE_RELEASE_ID="hhh-authoritative-2026-07-19-v1"
```

## 1. Local validation (no database or Jina writes)

```bash
python scripts/ingest_authoritative_knowledge.py \
  --dry-run \
  --release-id "$AUTHORITATIVE_RELEASE_ID"
```

The report must show 25 sources (22 web and three documents), zero mock chunks,
and no validation errors. YAML front matter must not appear in chunk content.

## 2. Apply release metadata migration

Review `supabase/migrations/202607190001_authoritative_knowledge_provenance.sql`,
then apply only that idempotent migration:

```bash
python scripts/apply_authoritative_migration.py --yes
```

## 3. Stage embeddings without activation

This calls Jina with `retrieval.passage`, stores 1024-dimensional vectors, and
keeps every staged row inactive. Retrying the same release skips unchanged rows.

```bash
python scripts/ingest_authoritative_knowledge.py \
  --stage \
  --release-id "$AUTHORITATIVE_RELEASE_ID" \
  --yes
```

## 4. Verify and approve the staged release

This checks the exact allowlist, provenance, PDF/URL citation shape, vector
dimensions, inactive staging integrity, incomplete-source exclusion, and seven
golden lexical retrieval topics. The JSON report is redacted.

```bash
python scripts/verify_authoritative_knowledge.py \
  --release-id "$AUTHORITATIVE_RELEASE_ID" \
  --mark-verified \
  --report "migration-reports/authoritative-$AUTHORITATIVE_RELEASE_ID.json" \
  --yes
```

Do not activate if this command fails.

## 5. Activate atomically

```bash
python scripts/ingest_authoritative_knowledge.py \
  --activate \
  --release-id "$AUTHORITATIVE_RELEASE_ID" \
  --yes

python scripts/verify_authoritative_knowledge.py \
  --release-id "$AUTHORITATIVE_RELEASE_ID" \
  --expect-active \
  --report "migration-reports/authoritative-$AUTHORITATIVE_RELEASE_ID-active.json"
```

Activation makes the verified release active and retires legacy, non-selected,
predefined, and mock chunks in the same transaction.

## 6. Rollback rehearsal or recovery

Read `prior_release_id` from the verification report and run:

```bash
python scripts/ingest_authoritative_knowledge.py \
  --rollback \
  --release-id "$AUTHORITATIVE_RELEASE_ID" \
  --prior-release-id "<prior-release-id>" \
  --yes
```

Rollback is refused when the target release is missing, empty, or unverified.
After acceptance, changing the deployed `DATABASE_URL` is a separate manual
cutover. The application does not silently retry against the old database.
