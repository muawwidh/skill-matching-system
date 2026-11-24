"""Read-only labelling sample of live-job skill extraction, and its scoring.

`sample` draws a seeded random sample of active live jobs and writes, into a
new directory (normally under the git-ignored `evaluation/local/`):

- `labels.csv`: one `job` row per job (fill `missed_required_skills`) followed
  by one `skill` row per distinct extracted skill of that job (fill `label`
  with `correct` or `incorrect`);
- `postings.md`: each posting's text with its numbered extracted skills, to
  read while labelling;
- `gaps.csv`: an empty error log (header only) with the columns and allowed
  values in `GAP_COLUMNS` and `GAP_VALUES`; `job_id` is "J" plus the two-digit
  job number;
- `manifest.json`: seed, population, sampled job IDs, the allowed error-log
  values and the SHA-256 of the files as written.

Nothing is written to the database. `score` reads a labelled `labels.csv` and
reports extraction precision and the number of missed required skills.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Job, JobSkill
from app.job_sources import NON_LIVE_SOURCES
from app.repositories.document_repository import DocumentRepository

COLUMNS = ["row_type", "job_no", "skill_no", "job_id", "title", "company", "source", "posted_at", "external_url",
           "skill", "skill_type", "requirement", "occurrences", "status", "method", "taxonomy_link", "evidence",
           "label", "missed_required_skills"]
REQUIREMENT_STRENGTH = {"required": 3, "preferred": 2, "unknown": 1}
CORRECT = {"correct", "c", "yes", "y", "1"}
INCORRECT = {"incorrect", "i", "no", "n", "0", "wrong"}
NONE_MISSED = {"none", "-", "0"}
GAP_COLUMNS = ["job_id", "type", "term", "category", "cause", "requirement", "evidence"]
GAP_VALUES = {
    "type": ["missed", "false_positive", "wrong_mapping"],
    "category": ["technical_skill", "business_skill", "tool", "language", "certification", "experience",
                 "qualification", "-"],
    "cause": ["not_in_vocabulary", "list_not_split", "pattern_missed", "no_language_rules",
              "certification_unnamed", "company_description", "boilerplate", "generic_term", "partial_span",
              "acronym_mislinked", "section_missed"],
    "requirement": ["required", "preferred", "responsibility", "-"],
}
INSTRUCTIONS = (
    "label: 'correct' if the posting asks for or mentions this as a skill/requirement of the role and the "
    "extracted text names it correctly; otherwise 'incorrect'. Leave blank = not labelled. "
    "missed_required_skills: required skills of the posting that are not in its skill rows, separated by ';'. "
    "Write 'none' when nothing is missed; blank = not labelled."
)


@dataclass(frozen=True)
class SampleResult:
    directory: Path
    population: int
    job_ids: list[UUID]
    skill_rows: int


def _live_jobs(db: Session) -> list[Job]:
    return list(db.scalars(select(Job).where(Job.source.not_in(sorted(NON_LIVE_SOURCES)),
                                             Job.status == "processed").order_by(Job.id)))


def _skill_groups(db: Session, job: Job) -> list[dict]:
    """Distinct extracted skills of a job (by normalized text and type), as shown in the UI groups."""
    skills = [s for s in db.scalars(select(JobSkill).where(JobSkill.job_id == job.id).order_by(JobSkill.id))
              if s.source == "extraction" and s.review_status != "rejected"]
    concepts = DocumentRepository(db).approved_skill_concepts("job", skills)
    groups: dict[tuple[str, str], dict] = {}
    for skill in skills:
        group = groups.setdefault((skill.normalized_text, skill.skill_type), {
            "skill": skill.normalized_text, "skill_type": skill.skill_type, "requirement": "unknown",
            "occurrences": 0, "statuses": set(), "methods": set(), "links": set(), "evidence": ""})
        group["occurrences"] += 1
        group["statuses"].add(skill.review_status)
        if skill.extracted_term is not None:
            group["methods"].add(skill.extracted_term.extraction_method)
        if skill.id in concepts:
            group["links"].add(concepts[skill.id][1])
        if REQUIREMENT_STRENGTH.get(skill.requirement_type, 0) > REQUIREMENT_STRENGTH.get(group["requirement"], 0):
            group["requirement"] = skill.requirement_type
        if not group["evidence"] and skill.evidence_sentence:
            group["evidence"] = " ".join(skill.evidence_sentence.split())[:300]
    return sorted(groups.values(), key=lambda g: (g["skill"], g["skill_type"]))


def _status(statuses: set[str]) -> str:
    return "approved" if "approved" in statuses else "automatic"


def sample(db: Session, out_dir: Path, size: int = 20, seed: int = 20261121) -> SampleResult:
    """Write a labelling sample of `size` live jobs to the new directory `out_dir`. Read-only on the database."""
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"{out_dir} exists and is not empty; labels are never overwritten.")
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET TRANSACTION READ ONLY"))
    try:
        population = _live_jobs(db)
        if len(population) < size:
            raise ValueError(f"Only {len(population)} active live jobs; cannot sample {size}.")
        chosen = random.Random(seed).sample(population, size)
        rows: list[dict] = []
        postings: list[str] = []
        skill_rows = 0
        for job_no, job in enumerate(chosen, start=1):
            groups = _skill_groups(db, job)
            posted = job.posted_at.date().isoformat() if job.posted_at else ""
            rows.append({"row_type": "job", "job_no": job_no, "skill_no": "", "job_id": str(job.id),
                         "title": job.title, "company": job.company, "source": job.source, "posted_at": posted,
                         "external_url": job.external_url or "", "occurrences": len(groups),
                         "missed_required_skills": ""})
            lines = [f"## Job {job_no}: {job.title}", "",
                     f"{job.company} · {job.location} · {job.source} · posted {posted or 'unknown'}",
                     f"Job ID: {job.id}", f"Original posting: {job.external_url or '-'}", "",
                     "### Extracted skills", ""]
            for skill_no, group in enumerate(groups, start=1):
                skill_rows += 1
                rows.append({"row_type": "skill", "job_no": job_no, "skill_no": skill_no, "job_id": str(job.id),
                             "skill": group["skill"], "skill_type": group["skill_type"],
                             "requirement": group["requirement"], "occurrences": group["occurrences"],
                             "status": _status(group["statuses"]), "method": "; ".join(sorted(group["methods"])),
                             "taxonomy_link": "; ".join(sorted(group["links"])), "evidence": group["evidence"],
                             "label": ""})
                lines.append(f"{skill_no}. {group['skill']} ({group['skill_type']}, {group['requirement']})")
            lines += ["", "### Posting text", "", job.cleaned_description or job.description, "", "---", ""]
            postings.append("\n".join(lines))
    finally:
        db.rollback()

    out_dir.mkdir(parents=True, exist_ok=True)
    labels = out_dir / "labels.csv"
    with labels.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in COLUMNS})
    with (out_dir / "gaps.csv").open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(GAP_COLUMNS)
    gap_help = "gaps.csv (one row per error; job_id = J01..J{:02d}): ".format(size) + "; ".join(
        f"{column} = {' | '.join(values)}" for column, values in GAP_VALUES.items())
    (out_dir / "postings.md").write_text(
        f"# Live job extraction sample (seed {seed}, {size} jobs)\n\n{INSTRUCTIONS}\n\n{gap_help}\n\n"
        + "\n".join(postings),
        encoding="utf-8")
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "seed": seed, "size": size,
                "population": len(population), "population_rule": "active (processed) jobs with a live source",
                "job_ids": [str(job.id) for job in chosen], "skill_rows": skill_rows, "instructions": INSTRUCTIONS,
                "gaps_columns": GAP_COLUMNS, "gaps_allowed_values": GAP_VALUES,
                "sha256": {name: hashlib.sha256((out_dir / name).read_bytes()).hexdigest()
                           for name in ("labels.csv", "postings.md", "gaps.csv")}}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return SampleResult(out_dir, len(population), [job.id for job in chosen], skill_rows)


def _missed(value: str) -> list[str] | None:
    """Missed required skills of one job; None when not labelled."""
    value = value.strip()
    if not value:
        return None
    if value.casefold() in NONE_MISSED:
        return []
    items = [" ".join(part.split()) for part in re.split(r"[;\n]", value)]
    return list(dict.fromkeys(item.casefold() for item in items if item))


def _precision(counts: Counter) -> dict:
    labelled = counts["correct"] + counts["incorrect"]
    return {"correct": counts["correct"], "incorrect": counts["incorrect"], "labelled": labelled,
            "precision": round(counts["correct"] / labelled, 4) if labelled else None}


def score(labels_path: Path) -> dict:
    """Precision of extracted skills and missed required skills from a labelled `labels.csv`."""
    with labels_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or set(COLUMNS) - set(rows[0]):
        raise ValueError(f"{labels_path} is not a labelling file (missing columns).")
    overall: Counter = Counter()
    by: dict[str, dict[str, Counter]] = {"skill_type": defaultdict(Counter), "requirement": defaultdict(Counter),
                                         "status": defaultdict(Counter)}
    invalid: list[str] = []
    unlabelled_skills = 0
    jobs_labelled, missed_per_job = 0, []
    for line, row in enumerate(rows, start=2):
        if row["row_type"] == "job":
            missed = _missed(row["missed_required_skills"])
            if missed is not None:
                jobs_labelled += 1
                missed_per_job.append(len(missed))
            continue
        value = row["label"].strip().casefold()
        if not value:
            unlabelled_skills += 1
            continue
        if value in CORRECT:
            outcome = "correct"
        elif value in INCORRECT:
            outcome = "incorrect"
        else:
            invalid.append(f"line {line}: {row['label']!r}")
            continue
        overall[outcome] += 1
        for key in by:
            by[key][row[key]][outcome] += 1
    if invalid:
        raise ValueError("Labels must be correct or incorrect: " + "; ".join(invalid[:20]))
    jobs = sum(row["row_type"] == "job" for row in rows)
    return {
        "jobs": jobs, "skill_rows": len(rows) - jobs, "unlabelled_skill_rows": unlabelled_skills,
        **_precision(overall),
        "by": {key: {name: _precision(counts) for name, counts in sorted(groups.items())}
               for key, groups in by.items()},
        "missed_required": {
            "jobs_labelled": jobs_labelled, "jobs_unlabelled": jobs - jobs_labelled,
            "total": sum(missed_per_job),
            "jobs_with_any": sum(1 for count in missed_per_job if count),
            "mean_per_job": round(sum(missed_per_job) / jobs_labelled, 2) if jobs_labelled else None,
        },
    }
