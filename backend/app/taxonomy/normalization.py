import re
import unicodedata


def normalize_taxonomy_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^a-z0-9+#.]+", " ", normalized)
    return " ".join(normalized.split())
