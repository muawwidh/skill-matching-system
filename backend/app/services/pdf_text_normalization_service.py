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
        "education and certifications",
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
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = self._split_inline_headings(normalized)
        normalized = self._deduplicate_blank_lines(normalized)
        return normalized.strip()

    def _split_inline_headings(self, text: str) -> str:
        alternatives = "|".join(re.escape(heading) for heading in sorted(self.HEADING_PATTERNS, key=len, reverse=True))
        pattern = re.compile(rf"(?<![A-Za-z])({alternatives})(?![A-Za-z])", re.IGNORECASE)
        lines: list[str] = []
        for line in text.split("\n"):
            headings = [
                match for match in pattern.finditer(line)
                if match.group(1) == match.group(1).upper()
            ]
            first_content = len(line) - len(line.lstrip())
            punctuated_pair = (
                len(headings) == 2
                and line[headings[0].end():headings[1].start()].rstrip().endswith((".", "!", "?", ";"))
            )
            if not headings or headings[0].start() != first_content:
                lines.append(line)
                continue
            if len(headings) < 3 and not punctuated_pair:
                lines.append(line)
                continue
            cursor = 0
            for match in headings:
                body = line[cursor:match.start()].strip()
                if body:
                    lines.append(body)
                lines.append(match.group(1))
                cursor = match.end()
            tail = line[cursor:].strip()
            if tail:
                lines.append(tail)
        return "\n".join(lines)

    @staticmethod
    def _deduplicate_blank_lines(text: str) -> str:
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text
