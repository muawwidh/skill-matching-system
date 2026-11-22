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
            "education and certifications",
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
        if text[: headings[0][0]].strip():
            sections.append(
                DetectedSection(
                    section_type="full_text",
                    heading="Full text",
                    content=text[: headings[0][0]],
                    start_char=0,
                    end_char=headings[0][0],
                    confidence_score=0.6,
                )
            )
        for index, (start, end, section_type, heading) in enumerate(headings):
            next_start = headings[index + 1][0] if index + 1 < len(headings) else len(text)
            span = text[end:next_start]
            content = span.strip()
            if content:
                content_start = end + len(span) - len(span.lstrip())
                sections.append(
                    DetectedSection(
                        section_type=section_type,
                        heading=heading,
                        content=content,
                        start_char=content_start,
                        end_char=content_start + len(content),
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


# ---- Job requirement segmentation (extraction contract v3) -------------
# Reuses the predeclared heading table of the frozen retrieval v2 template, plus the
# headings below. Text under excluded headings (benefits, EEO, application details) is
# not passed to extraction at all.
JOB_EXCLUDED_HEADINGS = (
    "benefits", "perks", "what we offer", "equal opportunity", "equal employment opportunity", "eeo",
    "how to apply", "application process", "application questions", "screening questions", "compensation",
    "salary", "pay range", "why join us",
    # Company values and culture statements describe the employer, not requirements.
    "values", "our values", "core values", "our core values", "company values", "our culture",
    "culture and values", "values and behaviours", "values & behaviours", "values and behaviors",
    "attributes aligned with core values", "attributes aligned with our values",
)
_JOB_EXTRA_HEADINGS = (
    ("must have", "requirements"), ("must haves", "requirements"), ("must-haves", "requirements"),
    ("qualifications", "requirements"), ("minimum qualifications", "requirements"),
    ("bonus", "preferences"), ("nice-to-have", "preferences"), ("nice to haves", "preferences"),
)
JOB_SEGMENT_TYPES = {
    "requirements": "required_skills",
    "preferences": "preferred_skills",
    "responsibilities": "responsibilities",
    "summary": "summary",
    "context": "summary",
}
JOB_SEGMENTATION_METHOD = "job_heading_rules@v3"
_MAX_HEADING_LENGTH = 70


def _job_heading_aliases() -> list[tuple[str, str]]:
    from app.retrieval.job_budget import HEADINGS

    pairs = {(alias, kind) for kind, aliases in HEADINGS.items() for alias in aliases}
    pairs |= set(_JOB_EXTRA_HEADINGS)
    pairs |= {(alias, "excluded") for alias in JOB_EXCLUDED_HEADINGS}
    # An excluded heading also listed as generic context (e.g. "benefits") is excluded.
    pairs = {(a, k) for a, k in pairs if not (k == "context" and a in JOB_EXCLUDED_HEADINGS)}
    return sorted(pairs, key=lambda pair: (-len(pair[0]), pair[0], pair[1]))


_JOB_ALIASES = _job_heading_aliases()
_INLINE_SEPARATOR = re.compile(r"[ \t]*(?::|[-–][ \t])[ \t]*(?=\S)")


def classify_job_heading(line: str) -> tuple[str, int] | None:
    """Return (heading class, offset where same-line content starts) or None.

    A heading stands alone on its line (optionally ending in ':' or '?') or,
    except for excluded headings, is followed by ':' / ' - ' and content on the
    same line. Bulleted lines are never headings.
    """
    stripped = line.strip()
    if not stripped or stripped[0] in "-*•·" and not stripped.startswith("**"):
        return None
    lead = len(line) - len(line.lstrip())
    body = stripped.strip("*#_ ").replace("’", "'")
    lead += stripped.find(body[:1]) if body else 0
    lower = body.lower()
    for alias, kind in _JOB_ALIASES:
        if not lower.startswith(alias):
            continue
        rest = body[len(alias):]
        if re.fullmatch(r"\s*\??\s*:?\s*\**", rest) and len(body) <= _MAX_HEADING_LENGTH:
            return kind, len(line)
        separator = _INLINE_SEPARATOR.match(rest)
        # Excluded headings must stand alone: an inline "Salary: ..." must not swallow what follows.
        if separator and kind != "excluded":
            return kind, lead + len(alias) + separator.end()
    from app.retrieval.job_budget import _GENERIC_HEADING

    if len(body) <= _MAX_HEADING_LENGTH:
        generic = _GENERIC_HEADING.fullmatch(body.rstrip(":?* "))
        if generic and not generic.group(2):
            word = generic.group(1).lower()
            return ("responsibilities" if word in {"responsibilities", "duties", "accountabilities"} else "requirements"), len(line)
    return None


def detect_job_segments(text: str) -> list[DetectedSection]:
    """Split a job description into requirement segments for extraction.

    Text before the first recognised heading (or a description without any)
    is `full_text`, whose requirement type stays unknown. Excluded segments are
    omitted, so nothing under them is extracted.
    """
    segments: list[tuple[str, str, int, int]] = []
    current_kind, current_heading, start, position = "full_text", "Full text", 0, 0
    for line in text.splitlines(keepends=True):
        classified = classify_job_heading(line.rstrip("\r\n"))
        if classified:
            segments.append((current_kind, current_heading, start, position))
            heading_text = line.rstrip("\r\n")[: classified[1]]
            current_kind, current_heading = classified[0], heading_text.strip().strip("*#:_-–? ")
            start = position + classified[1]
        position += len(line)
    segments.append((current_kind, current_heading, start, position))

    sections: list[DetectedSection] = []
    for kind, heading, segment_start, segment_end in segments:
        if kind == "excluded":
            continue
        span = text[segment_start:segment_end]
        content = span.strip()
        if not content:
            continue
        content_start = segment_start + len(span) - len(span.lstrip())
        sections.append(
            DetectedSection(
                section_type="full_text" if kind == "full_text" else JOB_SEGMENT_TYPES[kind],
                heading=heading,
                content=content,
                start_char=content_start,
                end_char=content_start + len(content),
                confidence_score=0.6 if kind == "full_text" else 1.0,
                extraction_method=JOB_SEGMENTATION_METHOD,
            )
        )
    return sections
