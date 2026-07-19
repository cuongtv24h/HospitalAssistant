# === TASK:WP-008:START ===
import math
from typing import List

def generate_dry_run_report(result, sources_processed=None, plan=None) -> str:
    """Produce a human-readable dry-run summary with detailed metrics."""
    web_count = sum(1 for s in (sources_processed or []) if getattr(s, "source_kind", "") == "web")
    doc_count = sum(1 for s in (sources_processed or []) if getattr(s, "source_kind", "") == "document")
    inc_sources = sum(1 for s in (sources_processed or []) if getattr(s, "extraction_incomplete", False))

    lines = [
        "=" * 60,
        "Authoritative Knowledge Ingestion Dry-Run Report",
        "=" * 60,
        f"  Total sources catalogued : {len(sources_processed or [])} (Web: {web_count}, Document: {doc_count})",
        f"  Incomplete sources       : {inc_sources}",
        f"  Total chunks generated   : {result.total_chunks}",
        f"  Answerable chunks        : {result.answerable_chunks}",
        f"  Non-answerable chunks    : {result.total_chunks - result.answerable_chunks}",
        f"  Mock chunks              : {result.mock_chunks}",
        f"  Errors                   : {len(result.errors)}",
        "-" * 60,
    ]
    
    if result.errors:
        lines.append("  Error details:")
        for err in result.errors:
            lines.append(f"    - {err}")
        lines.append("-" * 60)

    # Calculate token statistics
    tokens = [rec.token_count for rec in result.chunk_records if rec.token_count > 0]
    if tokens:
        tokens.sort()
        t_min = tokens[0]
        t_max = tokens[-1]
        n = len(tokens)
        t_med = tokens[n // 2] if n % 2 == 1 else (tokens[n // 2 - 1] + tokens[n // 2]) / 2.0
        largest_rec = max(result.chunk_records, key=lambda r: r.token_count, default=None)
        
        lines.extend([
            "  Token Statistics:",
            f"    Min tokens           : {t_min}",
            f"    Median tokens        : {t_med:.1f}",
            f"    Max tokens           : {t_max}",
            f"    Largest chunk ID     : {largest_rec.chunk_id if largest_rec else 'N/A'}",
            "-" * 60,
        ])

    # Split reasons and Quality Flags
    split_reasons = {}
    quality_flags_count = {}
    per_source_chunks = {}

    for rec in result.chunk_records:
        reason = getattr(rec, "split_reason", "unknown")
        split_reasons[reason] = split_reasons.get(reason, 0) + 1
        for flag in getattr(rec, "quality_flags", []):
            quality_flags_count[flag] = quality_flags_count.get(flag, 0) + 1
        per_source_chunks[rec.source_id] = per_source_chunks.get(rec.source_id, 0) + 1

    lines.append("  Split Reasons:")
    for rsn, count in sorted(split_reasons.items()):
        lines.append(f"    - {rsn:<20} : {count} chunks")

    lines.append("  Quality Flags:")
    if quality_flags_count:
        for flg, count in sorted(quality_flags_count.items()):
            lines.append(f"    - {flg:<20} : {count} chunks")
    else:
        lines.append("    - (None)")

    lines.append("-" * 60)
    lines.append("  Per-Source Chunk Counts:")
    for src, count in sorted(per_source_chunks.items()):
        lines.append(f"    - {src:<20} : {count} chunks")
    lines.append("-" * 60)

    if plan:
        lines.extend([
            "  Planned Database Operations:",
            f"    To Insert            : {len(plan.to_insert)}",
            f"    To Update            : {len(plan.to_update)}",
            f"    To Skip              : {len(plan.to_skip)}",
            f"    To Retire (Legacy)   : {len(plan.to_retire)}",
            "-" * 60,
        ])

    lines.append("=" * 60)
    return "\n".join(lines)

# === TASK:WP-008:END ===
