from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from .token_counter import TokenCounter

class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    CONTACT = "contact"

@dataclass
class SemanticBlock:
    type: BlockType
    text: str
    section_path: List[str] = field(default_factory=list)
    atomic: bool = False
    is_heading: bool = False
    token_count: int = 0

MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBERED_HEADING = re.compile(
    r"^(?P<label>(?:[IVXLCDM]+|\d+(?:\.\d+)*)(?:[.)]|\s*[-–:]))\s*(?P<title>\S.+)$",
    re.IGNORECASE,
)
CONTACT_RE = re.compile(r"(?i)^(?:liên hệ|hotline|email|địa chỉ|cơ sở)\b")
LIST_RE = re.compile(r"^\s*(?:[-+*·✔️]|\d+[.)])\s+")
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")

def _uppercase_heading(text: str) -> bool:
    if len(text) > 100 or len(text.split()) > 14 or text.endswith((".", ",", ";")):
        return False
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) >= 0.8

def _implicit_heading(text: str) -> Optional[Tuple[int, str]]:
    match = NUMBERED_HEADING.match(text)
    if match:
        label = match.group("label")
        title = match.group("title").strip()
        digits = re.match(r"\d+(?:\.\d+)*", label)
        level = 1 + (digits.group(0).count(".") if digits else 0)
        if len(text) <= 140 or title.endswith(":"):
            return level, text.strip()
    if _uppercase_heading(text):
        return 1, text.strip()
    return None

def _section_update(path: List[str], level: int, title: str) -> List[str]:
    level = max(1, level)
    parent = path[: level - 1]
    while len(parent) < level - 1:
        parent.append("")
    return parent + [title]

def parse_blocks(text: str, counter: Optional[TokenCounter] = None) -> List[SemanticBlock]:
    counter = counter or TokenCounter()
    lines = text.splitlines()
    blocks: List[SemanticBlock] = []
    section_path: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        heading = MARKDOWN_HEADING.match(line)
        if heading:
            level, title = len(heading.group(1)), heading.group(2).strip()
            section_path = _section_update(section_path, level, title)
            blocks.append(SemanticBlock(BlockType.HEADING, title, list(section_path), True, True, counter.count(title)))
            i += 1
            continue
        implicit = _implicit_heading(line)
        if implicit:
            level, title = implicit
            section_path = _section_update(section_path, level, title)
            blocks.append(SemanticBlock(BlockType.HEADING, title, list(section_path), True, True, counter.count(title)))
            i += 1
            continue
        if TABLE_RE.match(line):
            group = []
            while i < len(lines) and TABLE_RE.match(lines[i].strip()):
                group.append(lines[i].strip())
                i += 1
            value = "\n".join(group)
            blocks.append(SemanticBlock(BlockType.TABLE, value, list(section_path), atomic=True, token_count=counter.count(value)))
            continue
        if LIST_RE.match(line):
            group = []
            while i < len(lines):
                current = lines[i].strip()
                if LIST_RE.match(current):
                    group.append(current)
                    i += 1
                    while i < len(lines) and lines[i].strip() and not LIST_RE.match(lines[i].strip()):
                        continuation = lines[i].strip()
                        if MARKDOWN_HEADING.match(continuation) or _implicit_heading(continuation):
                            break
                        group.append(continuation)
                        i += 1
                elif not current:
                    i += 1
                    if i < len(lines) and LIST_RE.match(lines[i].strip()):
                        continue
                    break
                else:
                    break
            value = "\n".join(group)
            blocks.append(SemanticBlock(BlockType.LIST, value, list(section_path), atomic=True, token_count=counter.count(value)))
            continue
        group = [line]
        i += 1
        while i < len(lines) and lines[i].strip():
            candidate = lines[i].strip()
            if MARKDOWN_HEADING.match(candidate) or _implicit_heading(candidate) or LIST_RE.match(candidate) or TABLE_RE.match(candidate):
                break
            group.append(candidate)
            i += 1
        value = " ".join(group)
        kind = BlockType.CONTACT if CONTACT_RE.match(value) else BlockType.PARAGRAPH
        atomic = kind == BlockType.CONTACT
        blocks.append(SemanticBlock(kind, value, list(section_path), atomic=atomic, token_count=counter.count(value)))
    return blocks
