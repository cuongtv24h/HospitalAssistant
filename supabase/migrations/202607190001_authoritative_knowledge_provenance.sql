-- Migration: Authoritative Knowledge Provenance and Release Management
-- Date: 2026-07-19

-- The authoritative pipeline needs the lexical lane even on a fresh database.
alter table knowledge_chunks add column if not exists search_document tsvector
generated always as (
  to_tsvector(
    'simple',
    coalesce(content, '') || ' ' || coalesce(sub_topic, '') || ' ' ||
    coalesce(source_id, '') || ' ' || coalesce(source_path, '')
  )
) stored;

create index if not exists knowledge_chunks_search_document_idx
  on knowledge_chunks using gin (search_document);

create table if not exists corpus_releases (
  release_id text primary key,
  status text not null check (status in ('staging', 'staged', 'verified', 'active', 'retired', 'failed')),
  expected_source_count integer not null check (expected_source_count > 0),
  expected_chunk_count integer not null check (expected_chunk_count > 0),
  embedding_identity text not null,
  prior_release_id text references corpus_releases(release_id),
  staged_at timestamptz,
  verified_at timestamptz,
  activated_at timestamptz,
  retired_at timestamptz,
  verification_report jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- Preserve the currently active corpus as an explicit rollback target before
-- authoritative staging. This is a one-time compatibility bridge for rows
-- created before release metadata existed.
insert into corpus_releases (
  release_id, status, expected_source_count, expected_chunk_count,
  embedding_identity, staged_at, verified_at, activated_at
)
select
  'legacy-pre-authoritative', 'active', count(distinct source_id), count(*),
  'legacy:unknown', now(), now(), now()
from knowledge_chunks
where is_active = true
  and not exists (select 1 from corpus_releases where status = 'active')
having count(*) > 0
on conflict (release_id) do nothing;

update knowledge_chunks
set metadata = jsonb_set(metadata, '{corpus_release_id}', '"legacy-pre-authoritative"'::jsonb, true),
    updated_at = now()
where is_active = true
  and coalesce(metadata->>'corpus_release_id', '') = ''
  and exists (
    select 1 from corpus_releases
    where release_id = 'legacy-pre-authoritative' and status = 'active'
  );

-- There must never be two implicit active corpora.
create unique index if not exists corpus_releases_single_active_idx
  on corpus_releases ((status)) where status = 'active';

create index if not exists knowledge_chunks_metadata_gin_idx on knowledge_chunks using gin (metadata);
create index if not exists knowledge_chunks_release_active_idx on knowledge_chunks ((metadata->>'corpus_release_id'), is_active);
create index if not exists knowledge_chunks_source_kind_idx on knowledge_chunks ((metadata->>'source_kind'));
create index if not exists knowledge_chunks_answerable_idx on knowledge_chunks ((metadata->>'answerable'));
create index if not exists corpus_releases_status_idx on corpus_releases (status);
