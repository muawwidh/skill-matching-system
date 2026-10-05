import hashlib
import json
from dataclasses import dataclass


MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
TEMPLATE_VERSION = "e5-job-profile-v1"
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
