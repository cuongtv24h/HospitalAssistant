# === TASK:WP-008:START ===
import re
from functools import lru_cache

TOKENIZER_ID = "cl100k_base"

class TokenCounter:
    """Pinned token counter using tiktoken cl100k_base with conservative fallback."""

    def __init__(self, encoding_name: str = TOKENIZER_ID):
        self.encoding_name = encoding_name
        try:
            import tiktoken
            self._encoding = tiktoken.get_encoding(encoding_name)
        except Exception:
            self._encoding = None
        self.effective_id = encoding_name if self._encoding is not None else "unicode-regex-v1"

    @lru_cache(maxsize=16384)
    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(text, disallowed_special=()))
        pieces = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        return max(1, int(len(pieces) * 1.35))
# === TASK:WP-008:END ===
