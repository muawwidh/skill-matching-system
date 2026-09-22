from dataclasses import dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class SkillDictionaryEntry:
    label: str
    term_type: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class ExtractedTerm:
    raw_text: str
    normalized_text: str
    term_type: str
    source_section: str
    evidence_sentence: str
    extraction_method: str
    confidence_score: float
    start_char: int
    end_char: int
    requirement_type: str = "unknown"


class SkillDictionary:
    def __init__(self, entries: list[SkillDictionaryEntry]) -> None:
        self.entries = entries

    @classmethod
    def from_json(cls, path: Path) -> "SkillDictionary":
        with path.open("r", encoding="utf-8") as stream:
            raw_entries = json.load(stream)
        return cls(
            [
                SkillDictionaryEntry(
                    label=item["label"],
                    term_type=item.get("type", "skill"),
                    aliases=tuple({item["label"].lower(), *item.get("aliases", [])}),
                )
                for item in raw_entries
            ]
        )


class SkillExtractor:
    def __init__(self, dictionary: SkillDictionary | None = None) -> None:
        dictionary_path = Path(__file__).resolve().with_name("skill_dictionary.json")
        self.dictionary = dictionary or SkillDictionary.from_json(dictionary_path)
        self.spacy_nlp = None
        self.spacy_matcher = None
        self._configure_spacy_matcher()

    def extract_from_sections(
        self,
        sections: list,
        full_text: str,
        document_kind: str,
    ) -> list[ExtractedTerm]:
        terms: list[ExtractedTerm] = []
        for section in sections:
            section_offset = self._section_offset(full_text, section.content, section.start_char)
            requirement_type = self._requirement_type(section.section_type, document_kind)
            terms.extend(
                self._extract_dictionary_terms(
                    section.content,
                    section.section_type,
                    section_offset,
                    requirement_type,
                )
            )
            terms.extend(
                self._extract_regex_terms(
                    section.content,
                    section.section_type,
                    section_offset,
                    requirement_type,
                )
            )
        return self._deduplicate(terms)

    def _extract_dictionary_terms(
        self,
        text: str,
        source_section: str,
        section_offset: int,
        requirement_type: str,
    ) -> list[ExtractedTerm]:
        terms: list[ExtractedTerm] = []
        if self.spacy_matcher is not None and self.spacy_nlp is not None:
            return self._extract_spacy_dictionary_terms(
                text,
                source_section,
                section_offset,
                requirement_type,
            )
        for entry in self.dictionary.entries:
            for alias in sorted(entry.aliases, key=len, reverse=True):
                pattern = re.compile(rf"(?<![A-Za-z0-9+#.-]){re.escape(alias)}(?![A-Za-z0-9+#.-])", re.I)
                for match in pattern.finditer(text):
                    start = section_offset + match.start()
                    end = section_offset + match.end()
                    terms.append(
                        ExtractedTerm(
                            raw_text=match.group(0),
                            normalized_text=entry.label.lower(),
                            term_type=entry.term_type,
                            source_section=source_section,
                            evidence_sentence=self._evidence_sentence(text, match.start(), match.end()),
                            extraction_method="dictionary",
                            confidence_score=0.9,
                            start_char=start,
                            end_char=end,
                            requirement_type=requirement_type,
                        )
                    )
        return terms

    def _extract_spacy_dictionary_terms(
        self,
        text: str,
        source_section: str,
        section_offset: int,
        requirement_type: str,
    ) -> list[ExtractedTerm]:
        doc = self.spacy_nlp(text)
        terms: list[ExtractedTerm] = []
        for match_id, start_token, end_token in self.spacy_matcher(doc):
            span = doc[start_token:end_token]
            label, term_type = self.spacy_nlp.vocab.strings[match_id].rsplit("::", 1)
            terms.append(
                ExtractedTerm(
                    raw_text=span.text,
                    normalized_text=label.lower(),
                    term_type=term_type,
                    source_section=source_section,
                    evidence_sentence=self._evidence_sentence(text, span.start_char, span.end_char),
                    extraction_method="spacy_phrase_matcher",
                    confidence_score=0.92,
                    start_char=section_offset + span.start_char,
                    end_char=section_offset + span.end_char,
                    requirement_type=requirement_type,
                )
            )
        return terms

    def _extract_regex_terms(
        self,
        text: str,
        source_section: str,
        section_offset: int,
        requirement_type: str,
    ) -> list[ExtractedTerm]:
        patterns = [
            ("experience_indicator", r"\b\d+\+?\s+(?:years?|yrs?)\s+(?:of\s+)?experience\b", 0.86),
            ("qualification", r"\b(?:bachelor|master|msc|bsc|phd|doctorate)\b(?:['’]s)?(?:\s+degree)?", 0.82),
            ("certification", r"\b(?:certified|certification|certificate|aws certified|azure certified)\b", 0.78),
        ]
        terms: list[ExtractedTerm] = []
        for term_type, pattern_text, confidence in patterns:
            for match in re.finditer(pattern_text, text, re.I):
                terms.append(
                    ExtractedTerm(
                        raw_text=match.group(0),
                        normalized_text=match.group(0).lower(),
                        term_type=term_type,
                        source_section=source_section,
                        evidence_sentence=self._evidence_sentence(text, match.start(), match.end()),
                        extraction_method="regex",
                        confidence_score=confidence,
                        start_char=section_offset + match.start(),
                        end_char=section_offset + match.end(),
                        requirement_type=requirement_type,
                    )
                )
        return terms

    @staticmethod
    def _section_offset(full_text: str, section_content: str, fallback_start: int) -> int:
        position = full_text.find(section_content)
        return position if position >= 0 else fallback_start

    @staticmethod
    def _requirement_type(section_type: str, document_kind: str) -> str:
        if document_kind != "job":
            return "candidate_evidence"
        if section_type == "required_skills":
            return "required"
        if section_type == "preferred_skills":
            return "preferred"
        return "unknown"

    @staticmethod
    def _evidence_sentence(text: str, start: int, end: int) -> str:
        sentence_start = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
        sentence_end_candidates = [position for position in [text.find(".", end), text.find("\n", end)] if position != -1]
        sentence_end = min(sentence_end_candidates) if sentence_end_candidates else len(text)
        sentence = text[sentence_start:sentence_end].strip()
        relative_start = max(start - sentence_start, 0)
        relative_end = max(end - sentence_start, relative_start)
        if len(sentence) > 140 or len(re.findall(r"[•,;|]", sentence)) >= 2:
            return SkillExtractor._evidence_list_item(sentence, relative_start, relative_end)
        return sentence

    @staticmethod
    def _evidence_list_item(sentence: str, start: int, end: int) -> str:
        delimiter_matches = list(re.finditer(r"[•,;|]", sentence))
        previous_delimiters = [match.end() for match in delimiter_matches if match.end() <= start]
        next_delimiters = [match.start() for match in delimiter_matches if match.start() >= end]
        fragment_start = max(previous_delimiters) if previous_delimiters else 0
        fragment_end = min(next_delimiters) if next_delimiters else len(sentence)
        fragment = sentence[fragment_start:fragment_end].strip()
        fragment = re.sub(
            r"^(?:skills|technical skills|core skills|key skills|professional skills)\s*[:\-•]*\s*",
            "",
            fragment,
            flags=re.I,
        ).strip()
        return fragment or sentence

    @staticmethod
    def _deduplicate(terms: list[ExtractedTerm]) -> list[ExtractedTerm]:
        best_terms: dict[tuple[str, str, str], ExtractedTerm] = {}
        for term in terms:
            key = (term.normalized_text, term.term_type, term.source_section)
            existing = best_terms.get(key)
            if existing is None or term.confidence_score > existing.confidence_score:
                best_terms[key] = term
        return sorted(best_terms.values(), key=lambda item: (item.start_char, item.normalized_text))

    def _configure_spacy_matcher(self) -> None:
        try:
            import spacy
            from spacy.matcher import PhraseMatcher
        except ImportError:
            return

        self.spacy_nlp = spacy.blank("en")
        self.spacy_matcher = PhraseMatcher(self.spacy_nlp.vocab, attr="LOWER")
        for entry in self.dictionary.entries:
            patterns = [self.spacy_nlp.make_doc(alias) for alias in entry.aliases]
            self.spacy_matcher.add(f"{entry.label}::{entry.term_type}", patterns)
