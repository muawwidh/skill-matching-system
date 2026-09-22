from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DetectedSection:
    section_type: str
    heading: str
    content: str
    start_char: int
    end_char: int
    confidence_score: float = 1.0
    extraction_method: str = "heading_rules"


class SectionDetectionService:
    HEADING_ALIASES: dict[str, tuple[str, ...]] = {
        "summary": (
            "summary",
            "profile",
            "professional summary",
            "career summary",
            "objective",
        ),
        "work_experience": (
            "experience",
            "work experience",
            "professional experience",
            "employment history",
            "employment",
        ),
        "education": (
            "education",
            "academic background",
            "academic qualifications",
            "qualifications and education",
        ),
        "skills": (
            "skills",
            "technical skills",
            "core skills",
            "key skills",
            "technologies",
        ),
        "certifications": ("certifications", "certificates", "licenses"),
        "projects": ("projects", "portfolio"),
        "responsibilities": ("responsibilities", "duties", "what you will do"),
        "required_skills": ("required skills", "requirements", "must have", "required qualifications"),
        "preferred_skills": ("preferred skills", "nice to have", "preferred qualifications"),
        "qualifications": ("qualifications", "minimum qualifications"),
    }

    def detect(self, text: str) -> list[DetectedSection]:
        headings = self._find_headings(text)
        if not headings:
            return [
                DetectedSection(
                    section_type="full_text",
                    heading="Full text",
                    content=text,
                    start_char=0,
                    end_char=len(text),
                    confidence_score=0.6,
                )
            ]

        sections: list[DetectedSection] = []
        for index, (start, end, section_type, heading) in enumerate(headings):
            next_start = headings[index + 1][0] if index + 1 < len(headings) else len(text)
            content = text[end:next_start].strip()
            if content:
                sections.append(
                    DetectedSection(
                        section_type=section_type,
                        heading=heading,
                        content=content,
                        start_char=end,
                        end_char=next_start,
                    )
                )
        return sections or [
            DetectedSection(
                section_type="full_text",
                heading="Full text",
                content=text,
                start_char=0,
                end_char=len(text),
                confidence_score=0.6,
            )
        ]

    def _find_headings(self, text: str) -> list[tuple[int, int, str, str]]:
        matches: list[tuple[int, int, str, str]] = []
        occupied_ranges: list[range] = []
        for section_type, aliases in self.HEADING_ALIASES.items():
            for alias in sorted(aliases, key=len, reverse=True):
                pattern = re.compile(
                    rf"(?im)^(?P<heading>{re.escape(alias)})[ \t]*(?P<separator>:|-)?[ \t]*"
                )
                for match in pattern.finditer(text):
                    if self._is_inside_existing_match(match.start(), occupied_ranges):
                        continue
                    if not self._looks_like_heading_match(text, match):
                        continue
                    heading = match.group("heading").strip()
                    matches.append((match.start(), match.end(), section_type, heading))
                    occupied_ranges.append(range(match.start(), match.end()))
        matches.sort(key=lambda item: item[0])
        return matches

    def _section_type_for_heading(self, heading: str) -> str | None:
        normalized = heading.lower().strip(": ")
        for section_type, aliases in self.HEADING_ALIASES.items():
            if normalized in aliases:
                return section_type
        return None

    @staticmethod
    def _is_inside_existing_match(position: int, occupied_ranges: list[range]) -> bool:
        return any(position in occupied_range for occupied_range in occupied_ranges)

    @staticmethod
    def _looks_like_heading_match(text: str, match: re.Match[str]) -> bool:
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        remaining_line = text[match.end() : line_end].strip()
        if match.group("separator"):
            return True
        return remaining_line == ""
