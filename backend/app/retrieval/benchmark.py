"""Offline, provenance-aware human relevance benchmark tooling."""

import csv
import hashlib
import json
import random
import re
from datetime import date
from pathlib import Path

from app.retrieval.evaluation import retrieval_metrics
from app.retrieval.representation import MODEL_ID, MODEL_REVISION, TEMPLATE_VERSION

SEED = 20261002
GRADE = {"0", "1", "2"}
CANDIDATE_FIELDS = ("id", "language", "profile_summary", "approved_skills", "source_category",
                    "consent_or_redistribution_status", "deidentification_notes")
JOB_FIELDS = ("id", "language", "title", "employer_label", "region_country", "employment_type",
              "required_skills", "preferred_skills", "description_paraphrase",
              "source_category", "access_date", "redistribution_status",
              "deidentification_notes")
JUDGMENT_FIELDS = ("candidate_id", "job_id", "relevance_grade", "reviewer_id",
                   "judgment_date", "rationale", "uncertainty_flag")
PII = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
                 r"(?<!\w)(?:\+?\d[\d .()\-]{8,}\d)(?!\w)", re.I)
ID = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")


def _jsonl(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            rows.append(row)
    return rows


def _text(row: dict, field: str, label: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip() or value.strip().upper() in {"TBD", "TODO", "UNKNOWN"}:
        raise ValueError(f"{label}: missing or placeholder {field}")
    return value.strip()


def _skills(row: dict, field: str, label: str) -> list[str]:
    values = row.get(field)
    if not isinstance(values, list) or any(not isinstance(x, str) or not x.strip() for x in values):
        raise ValueError(f"{label}: {field} must be an array of nonempty strings")
    return values


def _date(value: str, label: str) -> None:
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"{label}: invalid ISO date") from exc


def load_corpus(candidates_path: Path, jobs_path: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    candidates, jobs = {}, {}
    for row in _jsonl(candidates_path):
        label = f"candidate {row.get('id', '<missing>')}"
        for field in CANDIDATE_FIELDS:
            if field != "approved_skills":
                _text(row, field, label)
        identifier = row["id"]
        if not ID.fullmatch(identifier) or identifier in candidates:
            raise ValueError(f"{label}: invalid or duplicate ID")
        if row["language"] != "en":
            raise ValueError(f"{label}: initial benchmark supports language en only")
        if not _skills(row, "approved_skills", label):
            raise ValueError(f"{label}: no approved skills")
        evidence = row.get("approved_evidence_paraphrases", [])
        if not isinstance(evidence, list) or any(not isinstance(x, str) or not x.strip() for x in evidence):
            raise ValueError(f"{label}: invalid evidence paraphrases")
        canonical = row.get("canonical_taxonomy", [])
        if not isinstance(canonical, list) or any(not isinstance(x, dict) or
            not all(isinstance(x.get(k), str) and x[k].strip() for k in
                    ("source", "release", "concept_id", "preferred_label")) for x in canonical):
            raise ValueError(f"{label}: invalid canonical taxonomy references")
        if row["consent_or_redistribution_status"] not in {"consented", "redistributable", "author_paraphrase"}:
            raise ValueError(f"{label}: unacceptable consent/redistribution status")
        private = [row["profile_summary"], *row["approved_skills"], *evidence]
        if any(PII.search(x) for x in private):
            raise ValueError(f"{label}: possible personal identifier")
        candidates[identifier] = row
    for row in _jsonl(jobs_path):
        label = f"job {row.get('id', '<missing>')}"
        for field in JOB_FIELDS:
            if field not in {"required_skills", "preferred_skills"}:
                _text(row, field, label)
        identifier = row["id"]
        if not ID.fullmatch(identifier) or identifier in jobs:
            raise ValueError(f"{label}: invalid or duplicate ID")
        if row["language"] != "en":
            raise ValueError(f"{label}: initial benchmark supports language en only")
        required = _skills(row, "required_skills", label)
        preferred = _skills(row, "preferred_skills", label)
        if not required and not preferred:
            raise ValueError(f"{label}: no skill content")
        _date(row["access_date"], label)
        if row["redistribution_status"] not in {"redistributable", "author_paraphrase", "consented"}:
            raise ValueError(f"{label}: unacceptable redistribution status")
        url = row.get("source_url")
        if url is not None and (not isinstance(url, str) or not url.startswith(("https://", "http://"))):
            raise ValueError(f"{label}: invalid source URL")
        if row["source_category"] == "public_posting" and not url:
            raise ValueError(f"{label}: public posting requires source URL")
        if any(PII.search(x) for x in [row["title"], row["employer_label"], row["description_paraphrase"], *required, *preferred]):
            raise ValueError(f"{label}: possible personal identifier")
        jobs[identifier] = row
    if not candidates or not jobs:
        raise ValueError("Nonempty valid candidate and job corpora are required")
    return candidates, jobs


def pair_order(candidates: dict, jobs: dict, seed: int = SEED) -> list[tuple[str, str]]:
    pairs = [(c, j) for c in sorted(candidates) for j in sorted(jobs)]
    random.Random(seed).shuffle(pairs)
    return pairs


def write_blind_export(candidates: dict, jobs: dict, destination: Path, seed: int = SEED) -> dict:
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    metadata_path = destination.with_name(destination.name + ".metadata.json")
    if metadata_path.exists():
        raise FileExistsError(f"Refusing to overwrite {metadata_path}")
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=(*JUDGMENT_FIELDS, "candidate_summary",
                                                   "candidate_skills", "job_title", "job_region",
                                                   "job_required_skills", "job_preferred_skills",
                                                   "job_description"))
        writer.writeheader()
        for candidate_id, job_id in pair_order(candidates, jobs, seed):
            candidate, job = candidates[candidate_id], jobs[job_id]
            writer.writerow({"candidate_id": candidate_id, "job_id": job_id,
                             "candidate_summary": candidate["profile_summary"],
                             "candidate_skills": "; ".join(candidate["approved_skills"]),
                             "job_title": job["title"], "job_region": job["region_country"],
                             "job_required_skills": "; ".join(job["required_skills"]),
                             "job_preferred_skills": "; ".join(job["preferred_skills"]),
                             "job_description": job["description_paraphrase"]})
    metadata = {"seed": seed, "pair_count": len(candidates) * len(jobs),
                "ordering": "sorted IDs, Python random.Random(seed).shuffle",
                "rank_or_score_visible": False, "blind_csv_sha256": _sha256(destination)}
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def load_judgments(path: Path, candidates: dict, jobs: dict, require_complete: bool = True) -> dict[tuple[str, str], dict]:
    result = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(JUDGMENT_FIELDS).issubset(reader.fieldnames):
            raise ValueError("Judgment CSV missing required columns")
        for line_number, row in enumerate(reader, 2):
            key = (row["candidate_id"], row["job_id"])
            if key[0] not in candidates or key[1] not in jobs:
                raise ValueError(f"Judgment row {line_number}: unknown candidate/job ID")
            if key in result:
                raise ValueError(f"Judgment row {line_number}: duplicate pair")
            grade = row["relevance_grade"]
            if grade not in GRADE:
                if require_complete or grade.strip():
                    raise ValueError(f"Judgment row {line_number}: invalid or missing grade")
            else:
                for field in ("reviewer_id", "judgment_date", "rationale", "uncertainty_flag"):
                    _text(row, field, f"judgment row {line_number}")
                _date(row["judgment_date"], f"judgment row {line_number}")
                if row["uncertainty_flag"].lower() not in {"true", "false"}:
                    raise ValueError(f"Judgment row {line_number}: invalid uncertainty flag")
                if PII.search(row["rationale"]):
                    raise ValueError(f"Judgment row {line_number}: possible personal identifier")
            result[key] = row
    if require_complete:
        expected = {(c, j) for c in candidates for j in jobs}
        missing = expected - result.keys()
        if missing:
            raise ValueError(f"Missing {len(missing)} candidate-job judgments")
        for candidate_id in candidates:
            if not any(row["relevance_grade"] == "2" for (c, _), row in result.items() if c == candidate_id):
                raise ValueError(f"Candidate {candidate_id} has no grade-2 relevant job")
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_pack(candidates_path: Path, jobs_path: Path, judgments_path: Path,
                  rankings_path: Path, grade_one: bool = False,
                  allow_synthetic: bool = False) -> dict:
    candidates, jobs = load_corpus(candidates_path, jobs_path)
    judgments = load_judgments(judgments_path, candidates, jobs)
    if not allow_synthetic and (len(candidates), len(jobs), len(judgments)) != (8, 30, 240):
        raise ValueError("Phase 5 evaluation requires 8 candidates, 30 jobs and 240 judgments")
    ranked = {}
    for row in _jsonl(rankings_path):
        candidate_id = row.get("candidate_id")
        if candidate_id not in candidates or candidate_id in ranked:
            raise ValueError("Ranking has unknown or duplicate candidate ID")
        if (row.get("model_id"), row.get("model_revision"), row.get("template_version")) != (MODEL_ID, MODEL_REVISION, TEMPLATE_VERSION):
            raise ValueError("Ranking model/revision/template provenance mismatch")
        if row.get("corpus_sha256") != {"candidates": _sha256(candidates_path), "jobs": _sha256(jobs_path)}:
            raise ValueError("Ranking corpus checksum mismatch")
        ids = row.get("retrieved_job_ids")
        if not isinstance(ids, list) or len(ids) != len(set(ids)) or set(ids) != set(jobs):
            raise ValueError("Ranking must contain every benchmark job exactly once")
        ranked[candidate_id] = ids
    if set(ranked) != set(candidates):
        raise ValueError("Rankings missing candidate profiles")
    per_candidate = {}
    for candidate_id in sorted(candidates):
        relevant = {j for (c, j), row in judgments.items() if c == candidate_id and row["relevance_grade"] == "2"}
        measured = retrieval_metrics([{"relevant_job_ids": sorted(relevant),
                                      "retrieved_job_ids": ranked[candidate_id]}])
        per_candidate[candidate_id] = {"relevant_count": len(relevant), **measured}
    macro = {key: sum(row[key] for row in per_candidate.values()) / len(per_candidate)
             for key in ("recall_at_5", "recall_at_10", "recall_at_20", "mrr")}
    result = {"corpus": {"candidates": len(candidates), "jobs": len(jobs),
                         "judgments": len(judgments), "grade_2_relevant": sum(row["relevance_grade"] == "2" for row in judgments.values()),
                         "grade_1_partial": sum(row["relevance_grade"] == "1" for row in judgments.values())},
              "relevance_rule": "grade 2 only", "per_candidate": per_candidate,
              "macro_average": macro,
              "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "template_version": TEMPLATE_VERSION},
              "data_sha256": {name: _sha256(path) for name, path in
                              (("candidates", candidates_path), ("jobs", jobs_path),
                               ("judgments", judgments_path), ("rankings", rankings_path))}}
    if grade_one:
        exploratory = []
        for candidate_id in sorted(candidates):
            relevant = {j for (c, j), row in judgments.items() if c == candidate_id and row["relevance_grade"] in {"1", "2"}}
            exploratory.append(retrieval_metrics([{"relevant_job_ids": sorted(relevant),
                                                  "retrieved_job_ids": ranked[candidate_id]}]))
        result["exploratory_grade_1_or_2"] = {
            key: sum(row[key] for row in exploratory) / len(exploratory)
            for key in ("recall_at_5", "recall_at_10", "recall_at_20", "mrr")}
    return result


def export_rankings(candidates_path: Path, jobs_path: Path, mapping_path: Path,
                    database_url: str, destination: Path) -> dict:
    """Read actual retrieval results from an isolated database only."""
    from uuid import UUID

    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    from app.db.models import User
    from app.services.retrieval_service import RetrievalService

    if make_url(database_url).database != "phase5_verify":
        raise ValueError("Ranking export requires isolated phase5_verify database")
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    candidates, jobs = load_corpus(candidates_path, jobs_path)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if set(mapping.get("candidates", {})) != set(candidates) or set(mapping.get("jobs", {})) != set(jobs):
        raise ValueError("Evaluation-to-database mapping is incomplete or has unknown IDs")
    candidate_uuids = {key: UUID(value) for key, value in mapping["candidates"].items()}
    job_uuids = {key: UUID(value) for key, value in mapping["jobs"].items()}
    if len(set(candidate_uuids.values())) != len(candidates) or len(set(job_uuids.values())) != len(jobs):
        raise ValueError("Evaluation mapping contains duplicate database IDs")
    job_lookup = {value: key for key, value in job_uuids.items()}
    hashes = {"candidates": _sha256(candidates_path), "jobs": _sha256(jobs_path)}
    engine = create_engine(database_url, pool_pre_ping=True)
    rows = []
    try:
        with Session(engine) as db:
            service = RetrievalService(db)
            for candidate_id in sorted(candidates):
                user = db.get(User, candidate_uuids[candidate_id])
                if user is None:
                    raise ValueError(f"Missing database user for {candidate_id}")
                if user.status != "active" or not any(role.name == "candidate" for role in user.roles):
                    raise ValueError(f"Mapped user for {candidate_id} is not an active candidate")
                retrieved = service.jobs_for_user(user, len(jobs))
                ids = [job_lookup.get(item["job_id"]) for item in retrieved]
                if len(ids) != len(jobs) or set(ids) != set(jobs):
                    raise ValueError(f"Retrieval did not return every benchmark job for {candidate_id}; index first")
                rows.append({"candidate_id": candidate_id, "retrieved_job_ids": ids,
                             "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
                             "template_version": TEMPLATE_VERSION, "corpus_sha256": hashes})
    finally:
        engine.dispose()
    destination.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return {"candidate_count": len(rows), "job_count": len(jobs),
            "rankings_sha256": _sha256(destination), "corpus_sha256": hashes}


def cohens_kappa(first: Path, second: Path, candidates: dict, jobs: dict) -> dict:
    left = load_judgments(first, candidates, jobs)
    right = load_judgments(second, candidates, jobs)
    if {row["reviewer_id"] for row in left.values()} & {row["reviewer_id"] for row in right.values()}:
        raise ValueError("Second-reviewer IDs must differ from first-reviewer IDs")
    keys = sorted(left)
    observed = sum(left[key]["relevance_grade"] == right[key]["relevance_grade"] for key in keys) / len(keys)
    expected = sum(
        sum(left[key]["relevance_grade"] == grade for key in keys) *
        sum(right[key]["relevance_grade"] == grade for key in keys) / len(keys) ** 2
        for grade in GRADE)
    return {"pairs": len(keys), "observed_agreement": observed,
            "cohens_kappa": (observed - expected) / (1 - expected) if expected != 1 else None,
            "interpretation": "unweighted three-grade kappa; null when undefined"}
