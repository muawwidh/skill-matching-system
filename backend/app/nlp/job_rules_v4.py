"""Job extraction rules added in contract v4. CV extraction uses only the language rule.

- `list_items`: splits skill lists in requirement and preference sections into
  short items (at most four words) and returns those not already covered by
  another extracted term.
- v4.1: a split item is kept only if `ListVocabulary` knows it (curated
  dictionary, an ESCO skill/knowledge label, or an O*NET Technology Skills tool
  name); unknown items are dropped.
- `language_terms`: language names in a sentence with a proficiency cue.
- `certification_terms`: named certifications instead of the bare word.
- guards: a stoplist of generic terms; equal-opportunity and benefits sentences
  in every section; sentences about the company, privacy or the recruiting
  process outside the requirement sections.
- `is_short_acronym`: terms linked only by a case-sensitive exact label.

Every span is an offset into the section text it was found in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

LIST_SECTIONS = frozenset({"required_skills", "preferred_skills", "qualifications"})
MAX_ITEM_WORDS = 4

STOPLIST = frozenset({
    "it", "saas", "certification", "certifications", "certificate", "certificates", "certified",
    "application process", "application", "applications", "apply",
    "experience", "skills", "skill", "knowledge", "ability", "abilities", "degree", "tools", "tool",
    "technology", "technologies", "software", "solutions", "solution", "product", "products", "business",
    "data", "team", "teams", "work", "management", "development", "support", "environment",
    "fast-paced environment", "related field", "relevant field", "similar field", "equivalent",
    "equivalent experience", "similar", "others", "other", "etc", "plus", "a plus", "bonus", "nice to have",
    "must have", "required", "preferred", "advantage", "an advantage", "english language",
    "education", "qualifications", "qualification", "requirements", "responsibilities", "information", "digital",
    "mission", "values", "respect", "similarly", "candidate", "candidates", "role", "position", "job", "company",
    "opportunity", "growth", "impact", "culture", "people", "customers", "clients", "projects", "tasks",
    # Lone adjectives left by splitting, and places.
    "written", "spoken", "verbal", "oral", "analytical", "fast-paced", "dynamic", "autonomy", "service", "services",
    "germany", "uk", "usa", "us", "europe", "eu", "emea", "dach", "berlin", "london", "munich", "remote",
    "hybrid", "onsite", "on-site", "office",
})

# A sentence about the employer, the application or personal data, outside requirement sections.
_COMPANY_OR_RECRUITING = re.compile(
    r"\b(?:we are (?:a|an|the)\b|we['’]re (?:a|an|the)\b|founded in\b|headquartered\b|our (?:mission|vision|"
    r"customers|clients|investors|story|company)\b|backed by\b|(?:leading|global) provider of\b|"
    r"employees (?:in|across|worldwide)\b|offices (?:in|across)\b|personal data\b|privacy (?:policy|notice|"
    r"statement)\b|data protection (?:policy|notice|regulation|law)|gdpr\b|applicants?\b|apply (?:now|today|"
    r"via|through|here|online)\b|application (?:process|form)\b|recruit(?:er|ers|ment|ing)\b|equal opportunit|"
    r"reasonable accommodation|background check|visa sponsorship\b|hiring process\b|interview process\b)",
    re.I,
)

LANGUAGES = (
    "English", "German", "French", "Spanish", "Italian", "Dutch", "Portuguese", "Polish", "Swedish", "Danish",
    "Norwegian", "Finnish", "Czech", "Slovak", "Hungarian", "Romanian", "Bulgarian", "Greek", "Turkish",
    "Russian", "Ukrainian", "Lithuanian", "Latvian", "Estonian", "Croatian", "Serbian", "Slovenian", "Arabic",
    "Hebrew", "Chinese", "Mandarin", "Cantonese", "Japanese", "Korean", "Hindi", "Flemish", "Catalan",
    "Icelandic", "Luxembourgish", "Maltese", "Vietnamese", "Thai", "Indonesian", "Persian", "Urdu", "Bengali",
)
_LANGUAGE = re.compile(r"\b(?:" + "|".join(LANGUAGES) + "|" + "|".join(name.upper() for name in LANGUAGES) + r")\b")
_LANGUAGE_CUE = re.compile(
    r"\b(?:fluen(?:t|tly|cy)|proficien(?:t|cy)|native|mother tongue|bilingual|business[- ]level|"
    r"working (?:knowledge|proficiency)|professional (?:level|proficiency|working)|spoken|written|verbal|"
    r"speak(?:s|ing)?|speaker|languages?|command of|level|[ABC][12])\b",
    re.I,
)

# Names of certifications, matched with their spelling.
_CERTIFICATION_ACRONYMS = (
    "TOGAF", "PMP", "PRINCE2", "CISSP", "CISM", "CISA", "CCNA", "CCNP", "CCIE", "ITIL", "PSM", "CSPO", "PSPO",
    "CPA", "ACCA", "CFA", "CIMA", "CKA", "CKAD", "CKS", "OSCP", "CEH", "PMI-ACP", "CAPM", "ISTQB", "IPMA",
    "CIPP", "CIPM", "CRISC", "CGEIT", "GIAC", "SHRM-CP", "SHRM-SCP", "CPIM", "CSCP", "CDMP", "CCSP", "SSCP",
    "PgMP", "PfMP",
)
_NAME_TOKEN = r"[A-Z][\w+-]*"
_CERTIFICATIONS = [
    re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(a) for a in _CERTIFICATION_ACRONYMS) + r")(?![\w-])"),
    re.compile(r"\b(?:AWS|Azure|Microsoft|Google Cloud|Salesforce|Cisco|Oracle|Red Hat|Databricks|Snowflake|"
               r"HubSpot|Kubernetes|Scrum Alliance)\s+Certified(?:\s*:)?(?:\s+" + _NAME_TOKEN + r"){0,5}"),
    re.compile(r"\bCertified\s+(?:" + _NAME_TOKEN + r"\s+){0,4}" + _NAME_TOKEN),
    re.compile(r"\b(?:Lean\s+)?Six Sigma(?:\s+(?:Green|Black|Yellow)\s+Belt)?"),
    re.compile(r"\bCompTIA\s+[A-Z][\w]*\+?"),
    re.compile(r"(?:\b" + _NAME_TOKEN + r"\s+){1,4}(?:[Cc]ertification|[Cc]ertificate)s?\b"),
]
# Leading words that do not name a certification ("Relevant certification", "Any certificate").
_NOT_A_NAME = frozenset({
    "a", "an", "the", "any", "relevant", "valid", "appropriate", "industry", "recognised", "recognized",
    "professional", "formal", "equivalent", "additional", "other", "such", "similar", "related", "required",
    "preferred", "desirable", "your", "our", "this", "degree", "or", "and", "with", "have", "hold", "holding",
    "certification", "certificate", "certifications", "certificates", "technical", "official", "current",
})

_BULLET = re.compile(r"^\s*(?:[-*•·◦▪●–]|\d+[.)])\s+")
_LIST_CUE = re.compile(
    r"\b(?:with|in|of|using|including|includes|include|such as|like|e\.g\.?|eg\.|i\.e\.?|for example|"
    r"especially|particularly|across)\b\s*:?\s*|:\s*",
    re.I,
)
_SEPARATOR = re.compile(r"\s*(?:,|;|\||•|·|\(|\)|\band/or\b|\band\b|\bor\b|\s&\s|\betc\b\.?)\s*", re.I)
_LEAD_IN = re.compile(
    r"^(?:(?:e\.g\.?|eg\.|i\.e\.?|such as|including|like|especially|particularly|for example)\s*,?\s*)?"
    r"(?:(?:a|an|the)\s+)?(?:(?:very|highly)\s+)?"
    r"(?:(?:strong|excellent|good|great|solid|proven|demonstrated|deep|in-depth|thorough|basic|working|"
    r"advanced|hands-on|practical|extensive|broad|sound|relevant|prior|previous|professional|expert|"
    r"outstanding|exceptional|first-hand|some)\s+)*"
    r"(?:(?:knowledge|understanding|experience|expertise|proficiency|familiarity|background|skills?|"
    r"competence|command|grasp)\s+(?:of|in|with|using|on|around)\s+)?",
    re.I,
)
_TRAILING = re.compile(r"[\s.,:;!?'\"’”-]+$")
_TRAILING_QUALIFIER = re.compile(
    r"\s+(?:(?:is|are|would be|will be)\s+)?(?:(?:a|an|highly|strongly)\s+)*(?:preferred|required|"
    r"desirable|desired|mandatory|essential|plus|advantage|advantageous|beneficial|nice to have|"
    r"is a must|a must|welcome|appreciated|valued)\s*$", re.I)
_REJECT_WORDS = frozenset({
    "you", "we", "our", "your", "they", "us", "is", "are", "be", "being", "been", "will", "would", "can",
    "could", "should", "must", "may", "might", "to", "have", "has", "had", "who", "which", "that", "this",
    "these", "those", "if", "when", "where", "how", "what", "why", "able", "ability", "willingness", "willing",
    "eager", "desire", "passion", "passionate", "ideally", "preferably", "minimum", "least", "years", "year",
    "do", "does", "not", "within", "from", "into", "per", "via", "etc", "e.g", "i.e", "candidate", "final",
})
_DANGLING = frozenset({"for", "with", "of", "in", "to", "the", "a", "an", "and", "or", "at", "on", "by", "as",
                       "like", "such", "including", "e.g", "i.e", "our", "your", "their", "its", "into", "from"})
_DANGLING_START = frozenset({"at", "for", "on", "by", "as", "and", "or", "of", "with", "in", "to", "mr", "mrs",
                             "ms", "dr", "one", "two", "three", "some", "many", "several", "various", "all"})
# Equal-opportunity statements, benefits and legal eligibility text: never requirements, in any section.
_EEO_PHRASE = re.compile(
    r"\b(?:equal (?:employment )?opportunit|regardless of|without regard|irrespective of|protected "
    r"(?:veteran|characteristic|status)|affirmative action)", re.I)
_PROTECTED = re.compile(
    r"\b(?:race|colou?r|religion|creed|national origin|ancestry|gender identity|gender expression|sexual "
    r"orientation|marital status|veteran|disability|pregnancy|genetic information|citizenship|age|sex)\b", re.I)
_BENEFITS_OR_LEGAL = re.compile(
    r"\b(?:paid time off|pto\b|vacation days|public holidays|paid holidays|annual leave|parental leave|"
    r"401\(?k|pension (?:plan|scheme)|(?:health|life|legal|dental|vision) insurance|(?:medical|dental|vision) "
    r"(?:plans?|coverage)|stipend|salary|pay range|stock options|equity package|wellbeing|well-being|"
    r"work-life balance|flexible working|we offer\b|you will get\b|you['’]ll get\b|benefits (?:include|package)|"
    r"(?:our|employee) benefits|perks\b|export control|u\.s\. (?:citizen|person|national)|permanent resident|"
    r"asylum|work (?:permit|authori[sz]ation)|visa sponsorship|right to work|local currency|"
    r"flexible (?:locations|schedules|hours))", re.I)


def _eeo_or_benefits(sentence: str) -> bool:
    return bool(_EEO_PHRASE.search(sentence) or len(_PROTECTED.findall(sentence)) >= 2
                or _BENEFITS_OR_LEGAL.search(sentence))


_ABBREVIATION_END = re.compile(r"(?:\be\.g|\bi\.e|\betc|\bvs|\bapprox|\bincl|\bmrs?|\bms|\bdr|\b[A-Za-z])$", re.I)
# Contact lines ("Contact: Mr. Max Example, max@example.com") are never skill lists.
_CONTACT = re.compile(r"@|\b(?:contact|e-?mail|phone|tel|mobile|address)\b\s*:?|https?:|www\.", re.I)
_ACRONYM = re.compile(r"[A-Z][A-Z0-9&+]{1,4}")


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str
    normalized: str


def vocabulary_key(text: str) -> str:
    """Same normalisation as the taxonomy labels (casefold, punctuation except + # . to spaces)."""
    import unicodedata

    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"[^a-z0-9+#.]+", " ", normalized)
    return " ".join(normalized.split()).strip(".")


@dataclass(frozen=True)
class VocabularyHit:
    source: str  # dictionary | esco | onet_tool
    term_type: str  # skill | domain_knowledge | tool


class ListVocabulary:
    """Phrases a v4.1 list item must equal (after normalisation) to be kept.

    Sources, in priority order: the curated dictionary, ESCO skill/knowledge labels
    (preferred and alternative), O*NET Technology Skills tool names. A one-word
    ESCO label counts only if its concept is in the ESCO digital collection
    (otherwise "measurement", "curiosity", "design" would pass); one-word words
    from the dictionary or the O*NET tool list are unaffected. A one-word
    ESCO or O*NET entry that is published with capitals ("Go", "SAND", "Chef")
    matches only one of those spellings, so ordinary lower-case words are not
    taken for tool names.
    """

    def __init__(self, entries: dict[str, VocabularyHit], cased: dict[str, frozenset[str]]) -> None:
        self.entries = entries
        self.cased = cased

    @classmethod
    def build(cls, dictionary: list[tuple[str, str]] = (), esco: list[tuple[str, str]] = (),
              tools: list[str] = ()) -> "ListVocabulary":
        """`dictionary`: (alias, type); `esco`: (label, concept type skill|knowledge[, digital]); `tools`: names."""
        entries: dict[str, VocabularyHit] = {}
        forms: dict[str, set[str]] = {}
        for alias, term_type in dictionary:
            key = vocabulary_key(alias)
            if key:
                entries.setdefault(key, VocabularyHit("dictionary", term_type))
        esco_types: dict[str, set[str]] = {}
        for label, concept_type, *rest in esco:
            key = vocabulary_key(label)
            digital = bool(rest and rest[0])
            if " " not in key and not digital:
                continue  # one-word ESCO label outside the digital collection
            if key and key not in entries:
                esco_types.setdefault(key, set()).add(concept_type)
                if " " not in key:
                    forms.setdefault(key, set()).add(label.strip())
        for key, types in esco_types.items():
            entries[key] = VocabularyHit("esco", "skill" if "skill" in types else "domain_knowledge")
        for name in tools:
            key = vocabulary_key(name)
            if key and key not in entries:
                entries[key] = VocabularyHit("onet_tool", "tool")
                if " " not in key:
                    forms.setdefault(key, set()).add(name.strip())
        # Case-sensitive only when every published spelling has capitals.
        cased = {key: frozenset(spellings) for key, spellings in forms.items()
                 if entries[key].source != "dictionary" and all(f != f.lower() for f in spellings)}
        return cls(entries, cased)

    def __len__(self) -> int:
        return len(self.entries)

    def match(self, item: str) -> VocabularyHit | None:
        key = vocabulary_key(item)
        hit = self.entries.get(key)
        if hit is None:
            return None
        spellings = self.cased.get(key)
        if spellings and item.strip() not in spellings:
            return None
        return hit


def names_a_language(text: str) -> bool:
    """A language name in the item (handled by the language rule, not as a list item)."""
    return bool(_LANGUAGE.search(text))


def normalize_term(text: str) -> str:
    return " ".join(text.lower().split())


def is_short_acronym(raw_text: str) -> bool:
    """Two to five capitals or digits, e.g. "IT", "GTM", "AWS", "B2B"."""
    return bool(_ACRONYM.fullmatch(raw_text.strip()))


def is_stoplisted(normalized: str) -> bool:
    return normalized in STOPLIST


def sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """The sentence (or line) around a span."""
    left = max(text.rfind("\n", 0, start), *(text.rfind(mark + " ", 0, start) for mark in ".!?")) + 1
    candidates = [p for p in (text.find("\n", end), *(text.find(mark + " ", end) for mark in ".!?")) if p != -1]
    return left, (min(candidates) + 1 if candidates else len(text))


def in_company_or_recruiting_sentence(text: str, start: int, end: int) -> bool:
    left, right = sentence_bounds(text, start, end)
    return bool(_COMPANY_OR_RECRUITING.search(text[left:right]))


def in_eeo_or_benefits_sentence(text: str, start: int, end: int) -> bool:
    left, right = sentence_bounds(text, start, end)
    return _eeo_or_benefits(text[left:right])


_LANGUAGE_HEADING = re.compile(r"^[\W_]*(?:languages?|language skills|spoken languages)[\W_]*$", re.I)


def _language_blocks(text: str) -> list[tuple[int, int]]:
    """Spans of the lines under a "Languages" heading line, up to the next blank line (CVs)."""
    blocks, position, start = [], 0, None
    for line in text.split("\n"):
        end = position + len(line)
        if _LANGUAGE_HEADING.match(line):
            start = end
        elif start is not None and not line.strip():
            blocks.append((start, position))
            start = None
        position = end + 1
    if start is not None:
        blocks.append((start, len(text)))
    return blocks


def language_terms(text: str, cv: bool = False) -> list[Span]:
    """Language names in a sentence with a proficiency cue; in a CV also every name listed
    under a "Languages" heading."""
    found = []
    blocks = _language_blocks(text) if cv else []
    for match in _LANGUAGE.finditer(text):
        if any(start <= match.start() < end for start, end in blocks):
            found.append(Span(match.start(), match.end(), match.group(0), match.group(0).lower()))
            continue
        left, right = sentence_bounds(text, match.start(), match.end())
        sentence = text[left:right]
        relative = match.start() - left
        # The cue must be in the same sentence; the language name itself is not a cue.
        masked = sentence[:relative] + " " * (match.end() - match.start()) + sentence[relative + match.end() - match.start():]
        if _LANGUAGE_CUE.search(masked):
            found.append(Span(match.start(), match.end(), match.group(0), match.group(0).lower()))
    return found


def certification_terms(text: str) -> list[Span]:
    spans: list[Span] = []
    for pattern in _CERTIFICATIONS:
        for match in pattern.finditer(text):
            start, value = match.start(), match.group(0)
            tokens = value.split()
            while tokens and tokens[0].strip(":").lower() in _NOT_A_NAME:
                start = text.index(tokens[0], start) + len(tokens[0])
                tokens = tokens[1:]
            value = text[start:match.end()].lstrip(" :")
            start = match.end() - len(value)
            value = _TRAILING.sub("", value)
            if not value or value.lower().split()[0] in {"certification", "certificate", "certifications",
                                                         "certificates"}:
                continue
            spans.append(Span(start, start + len(value), value, normalize_term(value)))
    # Longest first; drop spans inside a longer one.
    spans.sort(key=lambda s: (-(s.end - s.start), s.start))
    kept: list[Span] = []
    for span in spans:
        if not any(other.start <= span.start and span.end <= other.end for other in kept):
            kept.append(span)
    return sorted(kept, key=lambda s: s.start)


def _sentences(line: str, offset: int) -> list[tuple[int, str]]:
    parts, start = [], 0
    for match in re.finditer(r"[.!?](?=\s+[A-Z(])", line):
        if _ABBREVIATION_END.search(line[start:match.start()]):
            continue
        parts.append((offset + start, line[start:match.start() + 1]))
        start = match.end()
    parts.append((offset + start, line[start:]))
    return parts


def _mask_defined_acronyms(sentence: str) -> str:
    """Blank out "(AI)" after "Artificial Intelligence", keeping offsets, so the long form stays one item."""
    def blank(match: re.Match) -> str:
        words = re.findall(r"[A-Za-z]+", match.group(1))
        acronym = match.group(2).rstrip("s")
        initials = "".join(word[0] for word in words[-len(acronym):]).upper() if len(words) >= len(acronym) else ""
        if initials == acronym.upper():
            return match.group(1) + " " * (len(match.group(0)) - len(match.group(1)))
        return match.group(0)
    return re.sub(r"((?:[A-Za-z][\w-]*\s+){1,5}?[A-Za-z][\w-]*)\s*\(([A-Z][A-Za-z]{1,6})\)", blank, sentence)


def _split_slash(segment: str) -> list[tuple[int, str]]:
    """Split on "/" except inside short or upper-case pairs such as CI/CD, UI/UX, TCP/IP, A/B."""
    pieces, start = [], 0
    for match in re.finditer(r"/", segment):
        spaced = segment[match.start() - 1:match.start()] == " " or segment[match.end():match.end() + 1] == " "
        left = re.search(r"[\w+#.-]*$", segment[:match.start()]).group(0)
        right = re.match(r"[\w+#.-]*", segment[match.end():]).group(0)
        if not spaced and (len(left) <= 3 or len(right) <= 3 or left.isupper() or right.isupper()):
            continue
        pieces.append((start, segment[start:match.start()]))
        start = match.end()
    pieces.append((start, segment[start:]))
    return pieces


def _clean_item(text: str, start: int) -> tuple[int, str]:
    stripped = text.lstrip(" \t\"'“‘(-–:")
    start += len(text) - len(stripped)
    lead = _LEAD_IN.match(stripped)
    if lead and lead.end():
        start += lead.end()
        stripped = stripped[lead.end():]
    stripped = _TRAILING.sub("", stripped).rstrip(")")
    stripped = _TRAILING.sub("", _TRAILING_QUALIFIER.sub("", stripped))
    return start, stripped


def _acceptable(item: str) -> bool:
    words = item.split()
    if not 1 <= len(words) <= MAX_ITEM_WORDS or not re.search(r"[A-Za-z]{2}", item):
        return False
    if re.search(r"[@<>=]|https?:|www\.|\d{3,}", item) or re.match(r"^\d", item):
        return False  # contact details, addresses, numbers
    if len(item) < 3 and not item.isupper():
        return False
    lowered = [word.strip(".,:;()").lower() for word in words]
    if any(word in _REJECT_WORDS for word in lowered):
        return False
    if lowered[-1] in _DANGLING or lowered[0] in _DANGLING_START:
        return False  # a fragment of a sentence: "experience with", "at Acme"
    return not is_stoplisted(normalize_term(item))


def _pieces(segment: str) -> list[tuple[int, str]]:
    """Split a list on separators. "written and verbal communication" stays whole: a one-word
    piece before "and"/"or" followed by a longer piece shares its head noun."""
    pieces: list[tuple[int, str]] = []
    cursor = 0
    for separator in _SEPARATOR.finditer(segment):
        left = segment[cursor:separator.start()]
        if re.fullmatch(r"\s*(?:and|or|and/or)\s*", separator.group(0), re.I) and len(left.split()) == 1:
            following = re.split(r"[,;|•·()]", segment[separator.end():], maxsplit=1)[0]
            if len(following.split()) >= 2:
                continue
        pieces.append((cursor, left))
        cursor = separator.end()
    pieces.append((cursor, segment[cursor:]))
    return pieces


def list_items(text: str) -> list[Span]:
    """Short skill items from a requirement or preference section.

    A bulleted line gives its own text as an item when it is short, or the items of
    its list. Other lines give items only from a list introduced by a cue ("with",
    "such as", "e.g.", ":"...). Prose without such a list gives nothing.
    """
    items: list[Span] = []
    position = 0
    for raw_line in text.split("\n"):
        line_offset = position
        position += len(raw_line) + 1
        bullet = _BULLET.match(raw_line)
        body_offset = line_offset + (bullet.end() if bullet else 0)
        body = raw_line[bullet.end():] if bullet else raw_line
        for sentence_offset, sentence in _sentences(body, body_offset):
            if (_eeo_or_benefits(sentence) or _COMPANY_OR_RECRUITING.search(sentence) or _CONTACT.search(body)
                    or language_terms(sentence)):
                # Language sentences are handled by the language rule ("written and spoken English").
                continue
            masked = _mask_defined_acronyms(sentence)
            separators = list(_SEPARATOR.finditer(masked))
            if separators:
                first = separators[0].start()
                cues = [cue for cue in _LIST_CUE.finditer(masked) if cue.end() <= first]
                if cues:
                    list_start = cues[-1].end()
                elif bullet:
                    list_start = 0
                else:
                    continue
            elif bullet:
                list_start = 0
            else:
                continue
            segment = masked[list_start:]
            for piece_start, piece in _pieces(segment):
                for slash_start, part in _split_slash(piece):
                    start, item = _clean_item(part, piece_start + slash_start)
                    if not _acceptable(item):
                        continue
                    absolute = sentence_offset + list_start + start
                    items.append(Span(absolute, absolute + len(item), text[absolute:absolute + len(item)],
                                      normalize_term(item)))
    return items
