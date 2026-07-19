# === TASK:WP-008:START ===
import yaml
from pathlib import Path
from typing import Dict, Tuple, Any

def read_markdown(path: Path) -> Tuple[Dict[str, Any], str]:
    """Read a markdown file, strip frontmatter, return (frontmatter_dict, body_text)."""
    content = path.read_text(encoding="utf-8")
    fm = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2].strip()
            try:
                fm = yaml.safe_load(fm_text) or {}
            except Exception:
                fm = {}
    return fm, body
# === TASK:WP-008:END ===
