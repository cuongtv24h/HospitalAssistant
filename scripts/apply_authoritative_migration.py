#!/usr/bin/env python3
"""Apply only the authoritative corpus release migration to DATABASE_URL."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.foundation.knowledge.ingestion.persistence.postgres import psycopg_connection_url, redact_connection_url

MIGRATION = ROOT / "supabase/migrations/202607190001_authoritative_knowledge_provenance.sql"
BASE_MIGRATION = ROOT / "supabase/migrations/202607180001_wp005_initial_schema.sql"
OPERATIONAL_MIGRATION = ROOT / "supabase/migrations/202607180005_operational_repository_metadata.sql"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Confirm the schema write")
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("Migration changes the database; rerun with --yes after reviewing the SQL file.")
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise SystemExit("DATABASE_URL is required.")
    print(f"Database target: {redact_connection_url(database_url)}")
    sql = MIGRATION.read_text(encoding="utf-8")
    import psycopg
    with psycopg.connect(
        psycopg_connection_url(database_url), prepare_threshold=None
    ) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.knowledge_chunks')")
                if cursor.fetchone()[0] is None:
                    print("Fresh database detected; applying the 1024-dimensional base schema.")
                    cursor.execute(BASE_MIGRATION.read_text(encoding="utf-8"))
                    cursor.execute(OPERATIONAL_MIGRATION.read_text(encoding="utf-8"))
                cursor.execute(sql)
                cursor.execute("SELECT to_regclass('public.corpus_releases')")
                if cursor.fetchone()[0] is None:
                    raise RuntimeError("corpus_releases was not created.")
    print(f"Applied migration: {MIGRATION.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
