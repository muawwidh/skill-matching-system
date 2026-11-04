import hashlib
import json
from dataclasses import dataclass, field


MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
TEMPLATE_V1 = "e5-job-profile-v1"
TEMPLATE_V2 = "e5-job-profile-v2"
TEMPLATES = (TEMPLATE_V1, TEMPLATE_V2)
TEMPLATE_VERSION = TEMPLATE_V2
DIMENSION = 384
MAX_TOKENS = 512


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def clean(value: str) -> str:
    return " ".join((value or "").split())


def unique_sorted(values: list[str]) -> list[str]:
    items = {clean(value) for value in values if clean(value)}
    return sorted(items, key=lambda value: (value.casefold(), value))


@dataclass(frozen=True)
class Representation:
    text: str
    source_hash: str
    taxonomy_fingerprint: str
    details: dict = field(default_factory=dict, compare=False)


def candidate_representation(rows: list[dict]) -> Representation | None:
    ordered = sorted(rows, key=lambda row: row["id"])
    approved = [row for row in ordered if row["status"] == "approved"]
    if not approved:
        return None
    skills = unique_sorted([value for row in approved for value in (row["text"], row.get("canonical", ""))])
    evidence = unique_sorted([row.get("evidence", "") for row in approved])
    releases = unique_sorted([row.get("release", "") for row in approved])
    parts = ["query: Skills: " + "; ".join(skills)]
    if evidence:
        parts.append("Evidence: " + "; ".join(evidence))
    return Representation("\n".join(parts), digest(ordered), digest(releases))


def job_representation(job: dict, rows: list[dict]) -> Representation:
    ordered = sorted(rows, key=lambda row: row["id"])
    included = [row for row in ordered if row["status"] != "rejected"]
    parts = ["passage: Job title: " + clean(job["title"])]
    for key, label in (("employment_type", "Employment"), ("location", "Location")):
        if clean(job.get(key, "")):
            parts.append(label + ": " + clean(job[key]))
    for requirement, label in (("required", "Required skills"), ("preferred", "Preferred skills"), ("unknown", "Other skills")):
        values = unique_sorted([value for row in included if row["requirement"] == requirement
                                for value in (row["text"], row.get("canonical", ""))])
        if values:
            parts.append(label + ": " + "; ".join(values))
    if clean(job.get("description", "")):
        parts.append("Description: " + clean(job["description"]))
    releases = unique_sorted([row.get("release", "") for row in included])
    return Representation("\n".join(parts), digest({"job": job, "skills": ordered}), digest(releases))


def bounded_text(text: str, tokenizer) -> str:
    """Keep the highest-priority prefix within 512 model tokens, including special tokens."""
    tokens = tokenizer.encode(text, add_special_tokens=True, truncation=False)
    if len(tokens) <= MAX_TOKENS:
        return text
    # E5's tokenizer uses one leading and one trailing special token.
    special = tokenizer.num_special_tokens_to_add(pair=False)
    content = tokens[1:1 + MAX_TOKENS - special]
    bounded = tokenizer.decode(content, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    while len(tokenizer.encode(bounded, add_special_tokens=True, truncation=False)) > MAX_TOKENS:
        content = content[:-1]
        bounded = tokenizer.decode(content, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    return bounded


# These aliases remain byte-for-byte baseline builders, including their hashes.
candidate_representation_v1 = candidate_representation
job_representation_v1 = job_representation


def resolve_template(version: str | None = None) -> str:
    if version is None:
        from app.core.config import settings
        version = settings.DENSE_TEMPLATE_VERSION
    if version not in TEMPLATES:
        raise ValueError("Unsupported retrieval template version")
    return version


def candidate_representation_v2(rows: list[dict]) -> Representation | None:
    baseline = candidate_representation_v1(rows)
    if baseline is None:
        return None
    return Representation(baseline.text, digest({"template": TEMPLATE_V2,
        "complete_v1_source_hash": baseline.source_hash, "text": baseline.text}), baseline.taxonomy_fingerprint)


def job_representation_v2(job: dict, rows: list[dict], sections: list[dict], tokenizer) -> Representation:
    from app.retrieval.job_budget import budget_job
    text, details = budget_job(job, rows, sections, tokenizer)
    included = [r for r in rows if r["status"] != "rejected"]
    release_hash = digest(unique_sorted([r.get("release", "") for r in included]))
    source_hash = digest({"template": TEMPLATE_V2, "model": MODEL_ID, "revision": MODEL_REVISION,
        "job": job, "skills": sorted(rows, key=lambda r: r["id"]),
        "sections": sorted(sections, key=lambda s: (s.get("start_char", 0), s.get("end_char", 0),
                                                    s.get("section_type", ""), s.get("content", ""), str(s.get("id", "")))),
        "text": text})
    return Representation(text, source_hash, release_hash, details)


def build_candidate_representation(rows: list[dict], template_version: str) -> Representation | None:
    version = resolve_template(template_version)
    return candidate_representation_v1(rows) if version == TEMPLATE_V1 else candidate_representation_v2(rows)


def build_job_representation(job: dict, rows: list[dict], sections: list[dict],
                             template_version: str, tokenizer=None) -> Representation:
    if resolve_template(template_version) == TEMPLATE_V1:
        return job_representation_v1(job, rows)
    if tokenizer is None:
        raise RuntimeError("Template v2 requires the pinned local tokenizer")
    return job_representation_v2(job, rows, sections, tokenizer)
