"""Predeclared v2 source selection, independent of jobs, candidates and relevance labels."""
import re

from app.retrieval.representation import MAX_TOKENS, clean, unique_sorted


METADATA_CAP = 104
STRUCTURED_CAP = 96
CLASS_WEIGHTS = {"requirements": 4, "preferences": 2, "responsibilities": 4, "summary": 1, "context": 1}
LABELS = {"requirements": "Source requirements", "preferences": "Source preferences",
          "responsibilities": "Source responsibilities", "summary": "Source summary", "context": "Source context"}
SECTION_TYPES = {"required_skills": "requirements", "qualifications": "requirements", "skills": "requirements",
    "education": "requirements", "certifications": "requirements", "preferred_skills": "preferences",
    "responsibilities": "responsibilities", "work_experience": "responsibilities", "summary": "summary"}
HEADINGS = {
    "requirements": ("requirements", "qualifications", "required qualifications", "minimum qualifications",
        "basic qualifications", "essential criteria", "person specification", "required skills", "skills",
        "technical skills", "skills and experience", "education and experience", "experience and qualifications",
        "what you bring", "what we're looking for", "what we are looking for", "what you'll need",
        "what you will need", "what you need", "your profile", "your qualifications", "about you", "who you are",
        "who we're looking for", "who we are looking for", "your skills and experience", "your background",
        "what you'll bring", "what you will bring", "essential qualifications", "essential skills",
        "ideal candidate", "the ideal candidate", "candidate profile"),
    "preferences": ("preferred qualifications", "preferred skills", "preferred experience", "desired skills", "desired qualifications", "nice to have",
        "desirable criteria", "desirable", "bonus points", "additional qualifications"),
    "responsibilities": ("responsibilities", "key responsibilities", "job responsibilities", "duties",
        "your responsibilities", "your tasks", "what you will do", "what you'll do", "what you do",
        "your role", "the role", "about the role", "role and responsibilities", "job description",
        "what you'll be doing", "what you will be doing", "your mission", "your impact", "key accountabilities"),
    "summary": ("summary", "overview", "job summary", "role overview", "position overview",
        "about this role", "about the position", "about the job"),
    "context": ("about us", "about the company", "our company", "benefits", "what we offer",
        "equal opportunity", "how to apply", "application process"),
}
_ALIASES = sorted(((h, k) for k, names in HEADINGS.items() for h in names), key=lambda p: (-len(p[0]), p[0]))
_REQUIREMENT = re.compile(r"^(?:[-*\u2022]\s*)?(?:must\b|you (?:have|hold|bring|are|can)\b|"
    r"(?:candidates?|applicants?) (?:must|should|need)\b|"
    r"(?:prior|previous|relevant) experience\b|(?:excellent|strong|good|proven|demonstrated)\b|"
    r"(?:\d+\+?\s+years?\b)|experience (?:in|with|of)\b|(?:working |good |strong |basic )?knowledge of\b|"
    r"(?:bachelor|master|phd|degree|proficiency|familiarity|ability to)\b)", re.I)
_DUTY = re.compile(r"^(?:[-*\u2022]\s*)?(?:you will\b|you.ll\b|(?:develop|design|build|maintain|"
    r"support|manage|perform|conduct|coordinate|analyze|analyse|implement|lead|collaborate|assist|deliver|"
    r"create|work|provide|evaluate|document|ensure|help|resolve|report|review|monitor|investigate|"
    r"participate|test|contribute|drive|execute|research)\b)", re.I)
_ROLE_CUE = re.compile(r"\b(?:responsible for|responsibilities include|duties include|in this role|"
    r"this role involves|you will|you.ll)\b", re.I)
_PREFERENCE_CUE = re.compile(r"\b(?:preferred|desirable|advantageous|nice to have|a plus|an advantage)\b", re.I)
_MANDATORY_CUE = re.compile(r"\b(?:required|mandatory|must|essential|minimum|at least|shall|needed)\b", re.I)
_QUALIFICATION_CUE = re.compile(r"\b(?:experience (?:with|in|of)|knowledge of|proficien(?:cy|t) (?:in|with)|"
    r"(?:bachelor|master|doctoral|phd)(?:['\u2019]s)?(?:\s+degree)?|years? (?:of )?experience)\b", re.I)
_GENERIC_HEADING = re.compile(r"(?:(?:your|our|key|main|core|essential|minimum|basic|technical|job|role|"
    r"candidate|professional|personal|additional)\s+)*(requirements|qualifications|skills|experience|"
    r"responsibilities|duties|accountabilities)\s*(?::\s*(.*))?", re.I)


def _count(text: str, tokenizer, special=False) -> int:
    return len(tokenizer.encode(text, add_special_tokens=special, truncation=False))


def _whole_line_preferred(line: str) -> bool:
    # Parenthetical/bracketed preferences do not establish the whole line's modality.
    body = re.sub(r"\([^()]*\)|\[[^\[\]]*\]", "", line)
    body = re.sub(r"^\s*[-*\u2022]\s*", "", body).strip()
    if not _PREFERENCE_CUE.search(body):
        return False
    mandatory = re.sub(r"\bnot (?:required|needed)\b", "", body, flags=re.I)
    if _MANDATORY_CUE.search(mandatory) or re.search(r"[.!?;]\s+\S", body):
        return False
    if re.search(r"[,;]\s*(?:with|where|while|although|but|and with)\b", body, re.I):
        return False
    if re.match(r"^(?:preferred|desirable|nice to have)\b", body, re.I):
        return True
    predicate = r"(?:preferred|desirable|advantageous|a plus|an advantage|nice to have)"
    if re.search(r"\b(?:is|are|would be|will be|is considered|are considered)\s+" + predicate + r"[.!]?\s*$", body, re.I):
        return True
    return False


def _clip(text: str, budget: int, tokenizer) -> str:
    if budget <= 0:
        return ""
    if _count(text, tokenizer) <= budget:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if _count(text[:mid], tokenizer) <= budget:
            low = mid
        else:
            high = mid - 1
    prefix = text[:low].rstrip()
    if low < len(text) and low and not text[low].isspace():
        space = prefix.rfind(" ")
        if space > 0:
            prefix = prefix[:space]
    while prefix and _count(prefix, tokenizer) > budget:
        prefix = prefix[:-1].rstrip()
    return prefix


def _allocate(total: int, weights: dict[str, int]) -> dict[str, int]:
    if not weights:
        return {}
    denominator = sum(weights.values())
    result = {k: total * w // denominator for k, w in weights.items()}
    for key in list(weights)[:total - sum(result.values())]:
        result[key] += 1
    return result


def _metadata(job: dict, tokenizer) -> str:
    values = [("passage: Job title", clean(job["title"]), 60),
              ("Employment", clean(job.get("employment_type", "")), 12),
              ("Location", clean(job.get("location", "")), 12)]
    rendered = "\n".join(label + ": " + _clip(value, cap, tokenizer) for label, value, cap in values if value)
    while _count(rendered, tokenizer) > METADATA_CAP:
        index = max(range(len(values)), key=lambda i: values[i][2])
        label, value, cap = values[index]
        if cap <= 1:
            raise ValueError("Tokenizer cannot represent mandatory job metadata within v2 budget")
        values[index] = label, value, cap - 1
        rendered = "\n".join(label + ": " + _clip(value, cap, tokenizer) for label, value, cap in values if value)
    return rendered


def _structured(rows: list[dict], tokenizer) -> tuple[str, set[str]]:
    groups = {}
    for kind, label in (("required", "Required skills"), ("preferred", "Preferred skills"), ("unknown", "Other skills")):
        values = unique_sorted([v for r in rows if r["status"] != "rejected" and r["requirement"] == kind
                                for v in (r["text"], r.get("canonical", ""))])
        dedup = {}
        for value in values:
            dedup.setdefault(value.casefold(), value)
        if dedup:
            groups[kind] = label, list(dedup.values())
    quotas = _allocate(STRUCTURED_CAP - 6, {k: {"required": 3, "preferred": 2, "unknown": 1}[k] for k in groups})
    lines = []
    represented = set()
    for kind, (label, values) in groups.items():
        cap = max(0, quotas[kind] - _count(label + ": ", tokenizer))
        body = _clip("; ".join(values), cap, tokenizer)
        if body:
            lines.append(label + ": " + body)
            represented.update(v.casefold() for v in values if v in body)
    return "\n".join(lines), represented


def _units(job: dict, sections: list[dict], represented: set[str]) -> tuple[dict, dict]:
    buckets = {kind: [] for kind in CLASS_WEIGHTS}
    seen = {kind: set() for kind in CLASS_WEIGHTS}
    report = {"heading_matches": 0, "cue_matches": 0, "duplicate_lines": 0, "structured_duplicates": 0}
    ordered = sorted(sections, key=lambda s: (s.get("start_char", 0), s.get("end_char", 0),
                                            s.get("section_type", ""), s.get("content", ""), str(s.get("id", ""))))
    if not ordered:
        ordered = [{"content": job.get("description", ""), "section_type": "full_text", "start_char": 0}]
    for section in ordered:
        inherited = SECTION_TYPES.get(section.get("section_type"), "context")
        for number, source_line in enumerate(section.get("content", "").splitlines()):
            line = clean(source_line)
            if not line:
                continue
            heading = None
            for alias, kind in _ALIASES:
                match = re.fullmatch(re.escape(alias) + r"\s*\??\s*(?::\s*(.*))?", line.replace("\u2019", "'"), re.I)
                if match:
                    heading = kind, line[match.start(1):match.end(1)] if match.group(1) else ""
                    break
            if heading is None:
                generic = _GENERIC_HEADING.fullmatch(line)
                if generic:
                    kind = "responsibilities" if generic[1].lower() in {"responsibilities", "duties", "accountabilities"} else "requirements"
                    heading = kind, generic[2] or ""
            if heading:
                inherited, line = heading
                report["heading_matches"] += 1
                if not line:
                    continue
            whole_line_preferred = _whole_line_preferred(line)
            mixed_preference = bool(_PREFERENCE_CUE.search(line)) and not whole_line_preferred
            # Split only sentence/semicolon whitespace, never technical dotted identifiers.
            sentences = re.split(r"(?<=[.!?;])\s+(?=[A-Z0-9])", line)
            parts = [" ".join(words[i:i+64]) for sentence in sentences for words in [sentence.split()]
                     for i in range(0, len(words), 64)]
            for part in parts:
                kind = inherited
                if whole_line_preferred:
                    kind = "preferences"
                    report["cue_matches"] += 1
                elif kind != "preferences" and not (mixed_preference and inherited != "context"):
                    if _REQUIREMENT.match(part) or _QUALIFICATION_CUE.search(part):
                        kind = "requirements"
                        report["cue_matches"] += 1
                    elif _DUTY.match(part) or _ROLE_CUE.search(part):
                        kind = "responsibilities"
                        report["cue_matches"] += 1
                key = clean(part).casefold()
                if key in seen[kind]:
                    report["duplicate_lines"] += 1
                    continue
                seen[kind].add(key)
                if key in represented:
                    report["structured_duplicates"] += 1
                    continue
                buckets[kind].append({"text": part, "source_section_start": section.get("start_char", 0), "line": number})
    report["fallback"] = ("stored/headings" if report["heading_matches"] or any(
        SECTION_TYPES.get(s.get("section_type")) for s in ordered) else
        "line-cues+stratified-context" if report["cue_matches"] else "stratified-context")
    return buckets, report


def _render_bucket(kind: str, units: list[dict], budget: int, tokenizer) -> tuple[str, list]:
    label = LABELS[kind] + ": "
    remaining = max(0, budget - _count(label, tokenizer) - 3)
    indices = sorted({0, (len(units) - 1) // 2, len(units) - 1})
    quotas = _allocate(remaining, {str(i): 1 for i in indices})
    pieces = {}
    for i in indices:
        value = _clip(units[i]["text"], quotas[str(i)], tokenizer)
        if value:
            pieces[i] = value
    # Reserve stratified anchors first, then spend unused quota on source-order units.
    for i in range(len(units)):
        if i in pieces:
            continue
        used = _count(label + "\n".join(pieces[k] for k in sorted(pieces)), tokenizer)
        value = _clip(units[i]["text"], max(0, budget - used - 2), tokenizer)
        if value:
            pieces[i] = value
    for i in sorted(pieces):
        used = _count(label + "\n".join(pieces[k] for k in sorted(pieces)), tokenizer)
        extra = max(0, budget - used - 2)
        if extra:
            pieces[i] = _clip(units[i]["text"], _count(pieces[i], tokenizer) + extra, tokenizer)
    selected = [{"source_section_start": units[i]["source_section_start"], "line": units[i]["line"],
                 "unit_index": i,
                 "retained_characters": len(pieces[i]), "original_characters": len(units[i]["text"])}
                for i in sorted(pieces)]
    return (label + "\n".join(pieces[i] for i in sorted(pieces)) if pieces else ""), selected


def budget_job(job: dict, rows: list[dict], sections: list[dict], tokenizer) -> tuple[str, dict]:
    if tokenizer.num_special_tokens_to_add(pair=False) != 2:
        raise ValueError("Unexpected pinned tokenizer special-token contract")
    metadata = _metadata(job, tokenizer)
    structured, represented = _structured(rows, tokenizer)
    buckets, report = _units(job, sections, represented)
    active = {k: w for k, w in CLASS_WEIGHTS.items() if buckets[k]}
    base = "\n".join(v for v in (metadata, structured) if v)
    budget = MAX_TOKENS - 2 - _count(base, tokenizer) - 12
    initial_tokens = None
    shrink_passes = 0

    def render(quotas):
        parts = [base]
        selected = {}
        for kind in active:
            value, trace = _render_bucket(kind, buckets[kind], quotas[kind], tokenizer)
            if value:
                parts.append(value)
            selected[kind] = trace
        return "\n".join(parts), selected

    while True:
        quotas = _allocate(max(0, budget), active)
        result, selected = render(quotas)
        size = _count(result, tokenizer, special=True)
        if initial_tokens is None:
            initial_tokens = size
        if size <= MAX_TOKENS:
            # Refund unused class quotas without sacrificing already reserved classes.
            for _ in range(len(active) + 1):
                spare = MAX_TOKENS - size - 4
                unfinished = {k: active[k] for k in active if len(selected[k]) < len(buckets[k]) or
                              any(t["retained_characters"] < t["original_characters"] for t in selected[k])}
                if spare < 8 or not unfinished:
                    break
                extra = _allocate(spare, unfinished)
                expanded = {k: v + extra.get(k, 0) for k, v in quotas.items()}
                trial, trace = render(expanded)
                trial_size = _count(trial, tokenizer, special=True)
                if trial_size > MAX_TOKENS or trial == result:
                    break
                result, selected, size, quotas = trial, trace, trial_size, expanded
            break
        shrink_passes += 1
        budget -= size - MAX_TOKENS + 2
        if budget < 0:
            raise ValueError("Mandatory v2 content exceeds model token budget")
    report.update(tokens=size, initial_tokens=initial_tokens, shrink_passes=shrink_passes,
                  allocations=quotas, selected=selected,
                  available_units={k: len(v) for k, v in buckets.items()},
                  substantive_classes_lost=[k for k in ("requirements", "preferences", "responsibilities")
                                            if buckets[k] and not selected.get(k)])
    return result, report
