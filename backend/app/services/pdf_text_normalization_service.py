import re


class PdfTextNormalizationService:
    HEADING_PATTERNS = (
        "professional summary",
        "career summary",
        "summary",
        "profile",
        "objective",
        "professional experience",
        "work experience",
        "employment history",
        "experience",
        "education",
        "academic background",
        "academic qualifications",
        "technical skills",
        "core skills",
        "key skills",
        "skills",
        "certifications",
        "certificates",
        "projects",
    )

    def normalize(self, text: str) -> str:
        normalized = text.replace("\r", "\n")
        normalized = self._split_inline_headings(normalized)
        normalized = self._deduplicate_blank_lines(normalized)
        return normalized.strip()

    def _split_inline_headings(self, text: str) -> str:
        normalized = text
        for heading in sorted(self.HEADING_PATTERNS, key=len, reverse=True):
            pattern = re.compile(
                rf"(?<!\n)(?<![A-Za-z])\b({re.escape(heading)})\b\s*:?",
                re.IGNORECASE,
            )
            normalized = pattern.sub(lambda match: f"\n{match.group(1).title()}:\n", normalized)
        return normalized

    @staticmethod
    def _deduplicate_blank_lines(text: str) -> str:
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text
