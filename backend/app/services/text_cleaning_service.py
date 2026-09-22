import re


class TextCleaningService:
    def clean(self, text: str) -> str:
        normalized = text.replace("\x00", " ")
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()
