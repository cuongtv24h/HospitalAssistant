from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List, Sequence, Optional
from ..models import SourceRecord, ChunkRecord
from .block_parser import parse_blocks, SemanticBlock, BlockType
from .token_counter import TokenCounter

CHUNKING_VERSION = "hhh-structure-v1"

@dataclass
class StructureChunkingConfig:
    min_tokens: int = 250
    target_tokens: int = 500
    max_tokens: int = 700
    overlap_tokens: int = 60

SENTENCE_SPLIT = re.compile(r"(?<=[.!?;:])\s+(?=[A-ZÀ-Ỹ0-9])")

def _split_oversized(block: SemanticBlock, config: StructureChunkingConfig, counter: TokenCounter) -> List[SemanticBlock]:
    if block.token_count <= config.max_tokens:
        return [block]
    
    if block.type in {BlockType.LIST, BlockType.TABLE}:
        parts = [part.strip() for part in block.text.splitlines() if part.strip()]
    else:
        parts = [part.strip() for part in SENTENCE_SPLIT.split(block.text) if part.strip()]
    
    if len(parts) <= 1:
        words = block.text.split()
        parts, current = [], []
        for word in words:
            trial = " ".join(current + [word])
            if current and counter.count(trial) > config.max_tokens:
                parts.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            parts.append(" ".join(current))

    output, current = [], []
    for part in parts:
        trial = "\n".join(current + [part])
        if current and counter.count(trial) > config.max_tokens:
            value = "\n".join(current)
            output.append(SemanticBlock(block.type, value, list(block.section_path), atomic=False, token_count=counter.count(value)))
            current = [part]
        else:
            current.append(part)
    if current:
        value = "\n".join(current)
        output.append(SemanticBlock(block.type, value, list(block.section_path), atomic=False, token_count=counter.count(value)))
    
    # Final safety check: if any output piece still > max_tokens, force word split
    final_output = []
    for p in output:
        if counter.count(p.text) > config.max_tokens:
            words = p.text.split()
            sub_curr = []
            for w in words:
                trial = " ".join(sub_curr + [w])
                if sub_curr and counter.count(trial) > config.max_tokens:
                    val = " ".join(sub_curr)
                    final_output.append(SemanticBlock(p.type, val, list(p.section_path), atomic=False, token_count=counter.count(val)))
                    sub_curr = [w]
                else:
                    sub_curr.append(w)
            if sub_curr:
                val = " ".join(sub_curr)
                final_output.append(SemanticBlock(p.type, val, list(p.section_path), atomic=False, token_count=counter.count(val)))
        else:
            final_output.append(p)

    return final_output


def _content(blocks: Sequence[SemanticBlock]) -> str:
    content = "\n\n".join(block.text for block in blocks if block.type != BlockType.HEADING).strip()
    if content:
        return content
    return "\n\n".join(block.text for block in blocks if block.type == BlockType.HEADING).strip()

def _tail_overlap(blocks: Sequence[SemanticBlock], config: StructureChunkingConfig) -> List[SemanticBlock]:
    selected: List[SemanticBlock] = []
    total = 0
    for block in reversed(blocks):
        if block.type == BlockType.HEADING or total + block.token_count > config.overlap_tokens:
            break
        selected.append(block)
        total += block.token_count
    return list(reversed(selected))

def chunk_source_record(
    source: SourceRecord,
    body_text: str,
    config: Optional[StructureChunkingConfig] = None,
    counter: Optional[TokenCounter] = None,
    release_id: str = "rel-latest"
) -> List[ChunkRecord]:
    config = config or StructureChunkingConfig()
    counter = counter or TokenCounter()
    raw_blocks = parse_blocks(body_text, counter)
    blocks: List[SemanticBlock] = []
    oversized = False
    for block in raw_blocks:
        pieces = _split_oversized(block, config, counter)
        if len(pieces) > 1:
            oversized = True
        blocks.extend(pieces)

    groups: List[tuple[List[SemanticBlock], str]] = []
    current: List[SemanticBlock] = []
    current_tokens = 0
    current_path: List[str] = []

    for position, block in enumerate(blocks):
        if block.type == BlockType.HEADING:
            if current and current_tokens >= config.min_tokens:
                groups.append((current, "strong_heading"))
                current, current_tokens = [], 0
            current_path = block.section_path
            if not current:
                current.append(block)
                current_tokens += block.token_count
            continue

        strong_change = bool(current and block.section_path != current_path and current_tokens >= config.min_tokens)
        overflow = bool(current and counter.count(_content(current + [block])) > config.max_tokens)
        target_boundary = bool(current and current_tokens >= config.target_tokens and block.section_path != current_path)

        if strong_change or overflow or target_boundary:
            reason = "max_tokens" if overflow else "strong_heading"
            groups.append((current, reason))
            overlap = [] if strong_change else _tail_overlap(current, config)
            current = overlap[:]
            current_tokens = sum(item.token_count for item in current)
            if counter.count(_content(current + [block])) > config.max_tokens:
                current, current_tokens = [], 0

        current.append(block)
        current_tokens = counter.count(_content(current))
        current_path = block.section_path

    if current:
        groups.append((current, "document_end"))

    merged: List[tuple[List[SemanticBlock], str]] = []
    for group, reason in groups:
        tokens = counter.count(_content(group))
        if merged and tokens < config.min_tokens:
            prior, prior_reason = merged[-1]
            if counter.count(_content(prior + group)) <= config.max_tokens:
                merged[-1] = (prior + group, prior_reason)
                continue
        merged.append((group, reason))

    chunk_records: List[ChunkRecord] = []
    for index, (group, reason) in enumerate(merged):
        text_content = _content(group)
        if not text_content:
            continue
        path = next((b.section_path for b in reversed(group) if b.section_path), [])
        path_label = " > ".join(part for part in path if part)

        embedding_text = f"Tài liệu: {source.title}"
        if path_label:
            embedding_text += f"\nMục: {path_label}"
        embedding_text += f"\n\n{text_content}"

        content_hash = hashlib.sha256(text_content.encode("utf-8")).hexdigest()
        raw_id = (
            f"{source.source_id}|{source.source_content_hash}|{content_hash}|"
            f"{path_label}|{index}|{CHUNKING_VERSION}|{counter.effective_id}"
        )
        ext_chunk_id = f"{source.source_id}:{hashlib.sha256(raw_id.encode()).hexdigest()[:16]}"

        quality_flags = list(source.quality_flags)
        if oversized:
            quality_flags.append("oversized_block_split")
        quality_flags = sorted(set(quality_flags))

        is_answerable = not source.extraction_incomplete

        rec = ChunkRecord(
            chunk_id=ext_chunk_id,
            external_chunk_id=ext_chunk_id,
            content=text_content,
            embedding_text=embedding_text,
            domain=source.domain_code or source.topic,
            sub_topic=path_label,
            source_id=source.source_id,
            source_kind=source.source_kind,
            title=source.title,
            display_name=source.display_name,
            source_url=source.source_url,
            ingestion_path=source.ingestion_path,
            publisher=source.publisher,
            topic=source.topic,
            section_path=path_label,
            source_section=path_label,
            version=source.version,
            is_active=False,
            approval_status="approved",
            effective_date=source.effective_date,
            crawled_at=source.crawled_at,
            source_content_hash=source.source_content_hash,
            content_hash=content_hash,
            source_path=source.ingestion_path,
            chunker_version=CHUNKING_VERSION,
            tokenizer=counter.effective_id,
            token_count=counter.count(text_content),
            split_reason=reason,
            quality_flags=quality_flags,
            extraction_incomplete=source.extraction_incomplete,
            answerable=is_answerable,
            is_mock=False,
            embedding_provider="jina",
            embedding_model="jina-embeddings-v5-text-small",
            embedding_dimensions=1024,
            embedding_identity="jina:jina-embeddings-v5-text-small:1024",
            corpus_release_id=release_id,
        )
        chunk_records.append(rec)

    return chunk_records
