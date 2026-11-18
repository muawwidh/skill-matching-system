from collections.abc import Iterable
from dataclasses import dataclass
import json
from pathlib import Path
import re

from app.taxonomy.normalization import normalize_taxonomy_text


# CV extraction stays on v2. Job extraction v3 (DECISIONS.md D038) adds heading-based
# requirement types, experience ranges and the optional ESCO label vocabulary.
EXTRACTION_CONTRACT_VERSION = "v2"
JOB_EXTRACTION_CONTRACT_VERSION = "v3"

_EXPERIENCE_V2 = r"\b\d+\+?\s+(?:years?|yrs?)\s+(?:of\s+)?experience\b"
# v3: ranges ("3-5", "1 to 3", "0–2"), "3+ years", and up to three words before "experience".
_EXPERIENCE_V3 = (
    r"\b\d+(?:\s*(?:-|–|to)\s*\d+)?\+?\s*(?:years?|yrs?)['’]?\s+(?:of\s+)?"
    r"(?:[a-z-]+\s+){0,3}?experience\b"
)
ESCO_DIGITAL_SCHEME = "http://data.europa.eu/esco/concept-scheme/6c930acd-c104-4ece-acf7-f44fd7333036"
ESCO_VOCABULARY_FILTER = "o7"
_ESCO_TOKEN = re.compile(r"[A-Za-z0-9+#.]+")


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
                    aliases=tuple(
                        sorted({item["label"].lower(), *item.get("aliases", [])}, key=lambda value: (value.casefold(), value))
                    ),
                )
                for item in raw_entries
            ]
        )


@dataclass(frozen=True)
class EscoConceptLabels:
    concept_type: str  # "skill" or "knowledge"
    reuse_level: str
    digital: bool
    labels: tuple[str, ...]  # preferred and alternative labels as published


@dataclass(frozen=True)
class _VocabularyEntry:
    term_type: str
    cased_forms: frozenset[str]


class EscoVocabulary:
    """ESCO skill/knowledge labels filtered by rule O7 (DECISIONS.md D038).

    A label is usable if its concept is in the ESCO Digital collection, or the
    label has at least two words and the concept is not transversal. Single-word
    labels must be at least two characters and, when ESCO spells them with
    capitals (e.g. "Python", "LESS"), must appear with one of those spellings.
    """

    MAX_TOKENS = 8

    def __init__(self, entries: dict[str, _VocabularyEntry], version: str) -> None:
        self.entries = entries
        self.version = version

    @classmethod
    def from_concepts(cls, concepts: Iterable[EscoConceptLabels], version: str) -> "EscoVocabulary":
        forms: dict[str, set[str]] = {}
        allowed: dict[str, set[str]] = {}
        for concept in concepts:
            for label in concept.labels:
                key = normalize_taxonomy_text(label)
                if not key:
                    continue
                if " " not in key:
                    forms.setdefault(key, set()).add(label.strip())
                multi_word = " " in key
                if concept.digital or (multi_word and concept.reuse_level != "transversal"):
                    if not multi_word and len(key) < 2:
                        continue
                    allowed.setdefault(key, set()).add(concept.concept_type)
        entries = {
            key: _VocabularyEntry(
                term_type="skill" if "skill" in types else "domain_knowledge",
                cased_forms=frozenset(f for f in forms.get(key, ()) if f != f.lower()) if " " not in key else frozenset(),
            )
            for key, types in allowed.items()
        }
        return cls(entries, version)

    def find(self, text: str) -> list[tuple[int, int, str, str]]:
        """Longest non-overlapping label matches within each line: (start, end, label, term_type)."""
        found: list[tuple[int, int, str, str]] = []
        for line in re.finditer(r"[^\n]+", text):
            tokens = []
            for match in _ESCO_TOKEN.finditer(line.group(0)):
                value = match.group(0).rstrip(".")
                if value:
                    start = line.start() + match.start()
                    tokens.append((value, start, start + len(value)))
            index = 0
            while index < len(tokens):
                for size in range(min(self.MAX_TOKENS, len(tokens) - index), 0, -1):
                    key = " ".join(token[0].lower() for token in tokens[index:index + size])
                    entry = self.entries.get(key)
                    if entry and (size > 1 or not entry.cased_forms or tokens[index][0] in entry.cased_forms):
                        found.append((tokens[index][1], tokens[index + size - 1][2], key, entry.term_type))
                        index += size
                        break
                else:
                    index += 1
        return found


class SkillExtractor:
    def __init__(self, dictionary: SkillDictionary | None = None, esco_vocabulary: EscoVocabulary | None = None) -> None:
        dictionary_path = Path(__file__).resolve().with_name("skill_dictionary.json")
        self.dictionary = dictionary or SkillDictionary.from_json(dictionary_path)
        self.esco_vocabulary = esco_vocabulary
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
        version = JOB_EXTRACTION_CONTRACT_VERSION if document_kind == "job" else EXTRACTION_CONTRACT_VERSION
        for section in sections:
            section_offset = self._section_offset(full_text, section.content, section.start_char)
            requirement_type = self._requirement_type(section.section_type, document_kind)
            dictionary_terms = self._extract_dictionary_terms(
                section.content,
                section.section_type,
                section_offset,
                requirement_type,
                version,
            )
            terms.extend(dictionary_terms)
            terms.extend(
                self._extract_regex_terms(
                    section.content,
                    section.section_type,
                    section_offset,
                    requirement_type,
                    version,
                )
            )
            if document_kind == "job" and self.esco_vocabulary is not None:
                terms.extend(
                    self._extract_esco_terms(
                        section.content, section.section_type, section_offset, requirement_type, dictionary_terms
                    )
                )
        return self._deduplicate(terms)

    def _extract_esco_terms(
        self,
        text: str,
        source_section: str,
        section_offset: int,
        requirement_type: str,
        dictionary_terms: list[ExtractedTerm],
    ) -> list[ExtractedTerm]:
        """ESCO label matches that do not overlap a curated dictionary match."""
        taken = [(term.start_char, term.end_char) for term in dictionary_terms]
        terms: list[ExtractedTerm] = []
        for start, end, label, term_type in self.esco_vocabulary.find(text):
            absolute = (section_offset + start, section_offset + end)
            if any(absolute[0] < other_end and other_start < absolute[1] for other_start, other_end in taken):
                continue
            terms.append(
                ExtractedTerm(
                    raw_text=text[start:end],
                    normalized_text=label,
                    term_type=term_type,
                    source_section=source_section,
                    evidence_sentence=self._evidence_sentence(text, start, end),
                    extraction_method=(
                        f"esco_vocabulary@{JOB_EXTRACTION_CONTRACT_VERSION}:"
                        f"{self.esco_vocabulary.version}:{ESCO_VOCABULARY_FILTER}"
                    ),
                    confidence_score=0.8,
                    start_char=absolute[0],
                    end_char=absolute[1],
                    requirement_type=requirement_type,
                )
            )
        return terms

    def _extract_dictionary_terms(
        self,
        text: str,
        source_section: str,
        section_offset: int,
        requirement_type: str,
        version: str = EXTRACTION_CONTRACT_VERSION,
    ) -> list[ExtractedTerm]:
        terms: list[ExtractedTerm] = []
        if self.spacy_matcher is not None and self.spacy_nlp is not None:
            return self._extract_spacy_dictionary_terms(
                text,
                source_section,
                section_offset,
                requirement_type,
                version,
            )
        for entry in self.dictionary.entries:
            for alias in sorted(entry.aliases, key=lambda value: (-len(value), value.casefold(), value)):
                pattern = re.compile(
                    rf"(?<![A-Za-z0-9+#.-]){re.escape(alias)}(?![A-Za-z0-9+#-]|\.(?=[A-Za-z0-9]))",
                    re.I,
                )
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
                            extraction_method=f"dictionary@{version}",
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
        version: str = EXTRACTION_CONTRACT_VERSION,
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
                    extraction_method=f"spacy_phrase_matcher@{version}",
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
        version: str = EXTRACTION_CONTRACT_VERSION,
    ) -> list[ExtractedTerm]:
        experience = _EXPERIENCE_V3 if version == JOB_EXTRACTION_CONTRACT_VERSION else _EXPERIENCE_V2
        patterns = [
            ("experience_indicator", experience, 0.86),
            ("qualification", r"\b(?:bachelor|master|msc|bsc|phd|doctorate)\b(?:['’]s)?(?:\s+degree)?", 0.82),
            ("certification", r"\b(?:certified|certification|certificate|aws certified|azure certified)\b", 0.78),
        ]
        terms: list[ExtractedTerm] = []
        for term_type, pattern_text, confidence in patterns:
            for match in re.finditer(pattern_text, text, re.I):
                terms.append(
                    ExtractedTerm(
                        raw_text=match.group(0),
                        normalized_text=(
                            " ".join(match.group(0).lower().split())
                            if version == JOB_EXTRACTION_CONTRACT_VERSION
                            else match.group(0).lower()
                        ),
                        term_type=term_type,
                        source_section=source_section,
                        evidence_sentence=self._evidence_sentence(text, match.start(), match.end()),
                        extraction_method=f"regex@{version}",
                        confidence_score=confidence,
                        start_char=section_offset + match.start(),
                        end_char=section_offset + match.end(),
                        requirement_type=requirement_type,
                    )
                )
        return terms

    @staticmethod
    def _section_offset(full_text: str, section_content: str, fallback_start: int) -> int:
        if full_text[fallback_start : fallback_start + len(section_content)] == section_content:
            return fallback_start
        position = full_text.find(section_content)
        return position if position >= 0 else fallback_start

    @staticmethod
    def _requirement_type(section_type: str, document_kind: str) -> str:
        if document_kind != "job":
            return "candidate_evidence"
        if section_type in {"required_skills", "qualifications"}:
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
