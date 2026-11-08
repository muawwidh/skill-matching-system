"""Offline, provenance-aware human relevance benchmark tooling."""

import csv
import hashlib
import json
import os
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from app.retrieval.evaluation import retrieval_metrics
from app.retrieval.evaluation_policy import load_policy, query_coverage, reviewer_limitations
from app.retrieval.representation import MODEL_ID, MODEL_REVISION, resolve_template

SEED = 20261002
GRADE = {"0", "1", "2"}
CANDIDATE_FIELDS = ("id", "language", "profile_summary", "approved_skills", "source_category",
                    "consent_or_redistribution_status", "deidentification_notes")
JOB_FIELDS = ("id", "language", "title", "employer_label", "region_country", "employment_type",
              "required_skills", "preferred_skills",
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


def _job_content(row: dict, label: str) -> tuple[str, str]:
    mode = row.get("content_mode", "paraphrased")
    if mode not in {"paraphrased", "verbatim_restricted"}:
        raise ValueError(f"{label}: invalid content_mode")
    if "description_text" in row:
        _text(row, "content_mode", label)
        _text(row, "description_text", label)
        # Validate without trimming: file hashes cover the exact serialized text.
        description = row["description_text"]
        if "description_paraphrase" in row and row["description_paraphrase"] != description:
            raise ValueError(f"{label}: conflicting description fields")
    elif mode == "paraphrased":
        _text(row, "description_paraphrase", label)
        description = row["description_paraphrase"]
    else:
        raise ValueError(f"{label}: verbatim_restricted requires description_text")
    status = _text(row, "redistribution_status", label)
    if mode == "verbatim_restricted":
        if "description_paraphrase" in row:
            raise ValueError(f"{label}: verbatim text must not be labelled description_paraphrase")
        if status != "restricted_internal_use" or row.get("redistribution_allowed") is not False:
            raise ValueError(f"{label}: verbatim_restricted requires restricted_internal_use and redistribution_allowed=false")
        if "redistribution" in row and row["redistribution"] is not False:
            raise ValueError(f"{label}: conflicting redistribution flag")
        if row.get("source_category") not in {"public_posting", "consented_job"}:
            raise ValueError(f"{label}: restricted text requires job-source provenance")
        for field in ("source_id", "source_url", "accessed_at", "pdf_filename", "pdf_sha256", "normalized_text_sha256"):
            _text(row, field, label)
        url = urlsplit(row["source_url"])
        if url.scheme not in {"https", "http"} or not url.netloc:
            raise ValueError(f"{label}: invalid provenance source URL")
        filename = row["pdf_filename"]
        if Path(filename).name != filename or "\\" in filename or not filename.lower().endswith(".pdf"):
            raise ValueError(f"{label}: pdf_filename must be a PDF basename")
        for field in ("pdf_sha256", "normalized_text_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", row[field]):
                raise ValueError(f"{label}: invalid {field}")
        if hashlib.sha256(description.encode("utf-8")).hexdigest() != row["normalized_text_sha256"]:
            raise ValueError(f"{label}: normalized text checksum mismatch")
        try:
            accessed = datetime.fromisoformat(row["accessed_at"])
            if accessed.utcoffset() != timedelta(0) or accessed.date().isoformat() != row["access_date"]:
                raise ValueError
        except ValueError as exc:
            raise ValueError(f"{label}: accessed_at must be UTC and match access_date") from exc
    elif status not in {"redistributable", "author_paraphrase", "consented"}:
        raise ValueError(f"{label}: unacceptable redistribution status for paraphrased content")
    return description, mode


def _job_has_pii(value: str) -> bool:
    for line in value.splitlines():
        updated = re.fullmatch(r"Updated (\d{2}\.\d{2}\.\d{4})", line.strip(), re.I)
        if updated:
            try:
                datetime.strptime(updated[1], "%d.%m.%Y")
                continue
            except ValueError:
                pass
        if PII.search(line) or re.match(r"\s*(?:name|recruiter|contact name)\s*:\s*\S", line, re.I):
            return True
    return False


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
        description, mode = _job_content(row, label)
        url = row.get("source_url")
        if url is not None and (not isinstance(url, str) or not url.startswith(("https://", "http://"))):
            raise ValueError(f"{label}: invalid source URL")
        if row["source_category"] == "public_posting" and not url:
            raise ValueError(f"{label}: public posting requires source URL")
        if any(_job_has_pii(x) for x in [row["title"], row["employer_label"], description, *required, *preferred]):
            raise ValueError(f"{label}: possible personal identifier")
        jobs[identifier] = {**row, "description_text": description, "content_mode": mode}
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
    contents = {key: _job_content(job, f"job {key}") for key, job in jobs.items()}
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=(*JUDGMENT_FIELDS, "candidate_summary",
                                                   "candidate_skills", "job_title", "job_region",
                                                   "job_required_skills", "job_preferred_skills",
                                                   "job_description", "job_content_mode",
                                                   "job_redistribution_status", "job_redistribution_allowed"))
        writer.writeheader()
        for candidate_id, job_id in pair_order(candidates, jobs, seed):
            candidate, job = candidates[candidate_id], jobs[job_id]
            writer.writerow({"candidate_id": candidate_id, "job_id": job_id,
                             "candidate_summary": candidate["profile_summary"],
                             "candidate_skills": "; ".join(candidate["approved_skills"]),
                             "job_title": job["title"], "job_region": job["region_country"],
                             "job_required_skills": "; ".join(job["required_skills"]),
                             "job_preferred_skills": "; ".join(job["preferred_skills"]),
                             "job_description": contents[job_id][0],
                             "job_content_mode": contents[job_id][1],
                             "job_redistribution_status": job["redistribution_status"],
                             "job_redistribution_allowed": False})
    metadata = {"seed": seed, "pair_count": len(candidates) * len(jobs),
                "ordering": "sorted IDs, Python random.Random(seed).shuffle",
                "rank_or_score_visible": False, "blind_csv_sha256": _sha256(destination),
                "contains_restricted_verbatim": any(mode == "verbatim_restricted" for _, mode in contents.values()),
                "redistribution_allowed": False, "usage": "private human labelling only; not a publication export"}
    fd = os.open(metadata_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return metadata


def load_judgments(path: Path, candidates: dict, jobs: dict, require_complete: bool = True, *,
                   policy_path: Path | None = None, candidates_path: Path | None = None,
                   jobs_path: Path | None = None) -> dict[tuple[str, str], dict]:
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
        policy = _bound_policy(policy_path, candidates_path, jobs_path, path, candidates, jobs, result)
        query_coverage(candidates, result, policy)
    elif policy_path is not None:
        raise ValueError("Evaluation policy requires complete judgment validation")
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound_policy(policy_path: Path | None, candidates_path: Path | None, jobs_path: Path | None,
                  judgments_path: Path, candidates: dict, jobs: dict, judgments: dict):
    if policy_path is None:
        return None
    if candidates_path is None or jobs_path is None:
        raise ValueError("Evaluation policy requires candidate and job corpus paths for checksum binding")
    if load_corpus(candidates_path, jobs_path) != (candidates, jobs):
        raise ValueError("Evaluation policy corpus objects do not match the bound files")
    return load_policy(policy_path, {"candidates": candidates_path, "jobs": jobs_path, "judgments": judgments_path},
                       [*candidates.values(), *jobs.values(), *judgments.values()])


def validate_benchmark(candidates_path: Path, jobs_path: Path, judgments_path: Path | None = None,
                       policy_path: Path | None = None) -> dict:
    candidates, jobs = load_corpus(candidates_path, jobs_path)
    result = {"candidates": len(candidates), "jobs": len(jobs), "expected_pairs": len(candidates) * len(jobs)}
    if judgments_path is None:
        if policy_path is not None:
            raise ValueError("Evaluation policy requires a judgment export")
        return result
    judgments = load_judgments(judgments_path, candidates, jobs, policy_path=policy_path,
                               candidates_path=candidates_path, jobs_path=jobs_path)
    policy = _bound_policy(policy_path, candidates_path, jobs_path, judgments_path, candidates, jobs, judgments)
    result.update(judged_pairs=len(judgments), query_coverage=query_coverage(candidates, judgments, policy),
                  reviewer_limitations=reviewer_limitations(judgments))
    if policy_path is not None:
        result["evaluation_policy_sha256"] = _sha256(policy_path)
    return result


def evaluate_pack(candidates_path: Path, jobs_path: Path, judgments_path: Path,
                  rankings_path: Path, grade_one: bool = False,
                  allow_synthetic: bool = False, template_version: str | None = None,
                  policy_path: Path | None = None) -> dict:
    template_version = resolve_template(template_version)
    candidates, jobs = load_corpus(candidates_path, jobs_path)
    judgments = load_judgments(judgments_path, candidates, jobs, policy_path=policy_path,
                               candidates_path=candidates_path, jobs_path=jobs_path)
    policy = _bound_policy(policy_path, candidates_path, jobs_path, judgments_path, candidates, jobs, judgments)
    coverage = query_coverage(candidates, judgments, policy)
    if not allow_synthetic and (len(candidates), len(jobs), len(judgments)) != (8, 30, 240):
        raise ValueError("Phase 5 evaluation requires 8 candidates, 30 jobs and 240 judgments")
    ranked = {}
    for row in _jsonl(rankings_path):
        candidate_id = row.get("candidate_id")
        if candidate_id not in candidates or candidate_id in ranked:
            raise ValueError("Ranking has unknown or duplicate candidate ID")
        if (row.get("model_id"), row.get("model_revision"), row.get("template_version")) != (MODEL_ID, MODEL_REVISION, template_version):
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
        if not relevant:
            exception = next(item for item in coverage["excluded_queries"] if item["candidate_id"] == candidate_id)
            per_candidate[candidate_id] = {"relevant_count": 0, "queries": 0, "status": "undefined",
                "reason": exception["reason"], **{key: None for key in ("recall_at_5", "recall_at_10", "recall_at_20", "mrr")}}
            continue
        measured = retrieval_metrics([{"relevant_job_ids": sorted(relevant),
                                      "retrieved_job_ids": ranked[candidate_id]}])
        per_candidate[candidate_id] = {"relevant_count": len(relevant), **measured}
    macro = {key: sum(per_candidate[candidate][key] for candidate in coverage["eligible_candidate_ids"])
             / coverage["aggregate_binary_query_denominator"]
             for key in ("recall_at_5", "recall_at_10", "recall_at_20", "mrr")}
    result = {"corpus": {"candidates": len(candidates), "jobs": len(jobs),
                         "judgments": len(judgments), "grade_2_relevant": sum(row["relevance_grade"] == "2" for row in judgments.values()),
                         "grade_1_partial": sum(row["relevance_grade"] == "1" for row in judgments.values())},
              "relevance_rule": "grade 2 only", "per_candidate": per_candidate,
              "query_coverage": coverage, "reviewer_limitations": reviewer_limitations(judgments),
              "macro_average": macro,
              "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "template_version": template_version},
              "data_sha256": {name: _sha256(path) for name, path in
                              (("candidates", candidates_path), ("jobs", jobs_path),
                               ("judgments", judgments_path), ("rankings", rankings_path))}}
    if policy_path is not None:
        result["data_sha256"]["evaluation_policy"] = _sha256(policy_path)
    if grade_one:
        exploratory = []
        exploratory_per_candidate = {}
        for candidate_id in sorted(candidates):
            relevant = {j for (c, j), row in judgments.items() if c == candidate_id and row["relevance_grade"] in {"1", "2"}}
            measured = (retrieval_metrics([{"relevant_job_ids": sorted(relevant),
                                            "retrieved_job_ids": ranked[candidate_id]}]) if relevant else None)
            exploratory_per_candidate[candidate_id] = {"relevant_count": len(relevant), "metrics": measured}
            if measured is not None:
                exploratory.append(measured)
        result["exploratory_grade_1_or_2"] = {
            key: sum(row[key] for row in exploratory) / len(exploratory)
            for key in ("recall_at_5", "recall_at_10", "recall_at_20", "mrr")}
        result["exploratory_per_candidate"] = exploratory_per_candidate
        result["exploratory_query_coverage"] = {"relevance_rule": "grade 1 or 2, separate from primary metrics",
            "total_queries": len(candidates), "aggregate_query_denominator": len(exploratory),
            "undefined_candidate_ids": [c for c, item in exploratory_per_candidate.items() if item["metrics"] is None]}
    return result


def export_rankings(candidates_path: Path, jobs_path: Path, mapping_path: Path,
                    database_url: str, destination: Path, template_version: str | None = None) -> dict:
    """Read actual retrieval results from an isolated database only."""
    from uuid import UUID

    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    from app.db.models import User
    from app.services.retrieval_service import RetrievalService
    template_version = resolve_template(template_version)

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
            service = RetrievalService(db, template_version)
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
                             "template_version": template_version, "corpus_sha256": hashes})
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
