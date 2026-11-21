"""Offline comparison of ranking variants on the frozen Phase 5 benchmark (D043).

Read-only: rankings are computed from the live database inside a read-only
transaction, and nothing is persisted. Every variant ranks the same 30 jobs
for the same candidates and is scored against the same frozen human
judgments, with the Phase 5 metric definitions plus nDCG@10.

Variants (no weights; each is a lexicographic order or a single score):
  A  retrieval only: cosine similarity (Phase 5), ties by job ID
  B  skill coverage, name matching only (taxonomy links ignored), ties by job ID
  C  skill coverage, taxonomy concept first then name (current rule), ties by job ID
  D  C with retrieval similarity as tie-break, then job ID (the app order until D044)
"""
import json
import math
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from app.job_sources import EVALUATION_SOURCE
from app.retrieval.benchmark import _sha256, _bound_policy, load_corpus, load_judgments
from app.retrieval.evaluation import retrieval_metrics
from app.retrieval.evaluation_policy import query_coverage
from app.retrieval.representation import MODEL_ID, MODEL_REVISION, resolve_template

VARIANTS = {
    "A": "retrieval only (cosine similarity), ties by job ID",
    "B": "skill coverage, name matching only, lexicographic, ties by job ID",
    "C": "skill coverage, taxonomy concept then name (current rule), lexicographic, ties by job ID",
    "D": "C with retrieval-similarity tie-break, then job ID (app order until D044)",
}
METRICS = ("recall_at_5", "recall_at_10", "recall_at_20", "mrr", "ndcg_at_10")
NO_SIGNIFICANCE = ("Seven evaluable queries, one rater: differences between variants are descriptive only. "
                   "No significance test was run and none would be meaningful at this sample size.")


def ndcg_at_k(ranked: list[str], grades: dict[str, int], k: int = 10) -> float | None:
    """nDCG@k with graded gain 2^grade - 1 and log2(rank + 1) discount (Järvelin & Kekäläinen).

    The ideal ordering sorts all judged jobs by grade. None when no job has a positive grade.
    """
    def dcg(values: list[int]) -> float:
        return sum((2 ** grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(values[:k], 1))

    ideal = dcg(sorted(grades.values(), reverse=True))
    if ideal == 0:
        return None
    return dcg([grades.get(job, 0) for job in ranked]) / ideal


def coverage_order(candidate_items: list, job_items: dict[str, list], job_db_ids: dict[str, UUID],
                   similarity: dict[str, float] | None = None, use_concepts: bool = True) -> list[str]:
    """Rank job aliases with the app's coverage rule and ranking key.

    use_concepts=False drops every taxonomy link on both sides, so only identical
    normalized names match. Without `similarity`, ties fall through to job ID.
    """
    from app.services.matching_service import compute_coverage, coverage_ranking_key

    def strip(items):
        return items if use_concepts else [replace(item, concept_id=None, concept_label=None) for item in items]

    candidate = strip(candidate_items)
    keyed = []
    for alias, items in job_items.items():
        result = compute_coverage(candidate, strip(items))
        match = SimpleNamespace(job_id=job_db_ids[alias], matched_required=result.matched_required,
                                missing_required=result.missing_required,
                                matched_preferred=result.matched_preferred,
                                missing_preferred=result.missing_preferred)
        keyed.append((coverage_ranking_key(match, (similarity or {}).get(alias)), alias))
    return [alias for _, alias in sorted(keyed)]


def score_rankings(rankings: dict[str, dict[str, list[str]]], judgments: dict, eligible: list[str]) -> dict:
    """Per-query and macro metrics for each variant over the eligible (evaluable) queries."""
    output = {}
    for variant, by_candidate in rankings.items():
        per_query = {}
        for candidate in eligible:
            ranked = by_candidate[candidate]
            grades = {job: int(row["relevance_grade"]) for (c, job), row in judgments.items() if c == candidate}
            relevant = sorted(job for job, grade in grades.items() if grade == 2)
            metrics = retrieval_metrics([{"relevant_job_ids": relevant, "retrieved_job_ids": ranked}])
            metrics.pop("queries")
            metrics["ndcg_at_10"] = ndcg_at_k(ranked, grades, 10)
            metrics["first_grade2_rank"] = next(rank for rank, job in enumerate(ranked, 1) if job in relevant)
            per_query[candidate] = metrics
        macro = {key: sum(per_query[c][key] for c in eligible) / len(eligible) for key in METRICS}
        # Exact fractions for the Phase 5 metrics (nDCG is irrational in general).
        exact = {}
        for key in METRICS[:4]:
            total = Fraction(0)
            for candidate in eligible:
                ranked = by_candidate[candidate]
                relevant = {job for (c, job), row in judgments.items() if c == candidate and row["relevance_grade"] == "2"}
                if key == "mrr":
                    total += Fraction(1, per_query[candidate]["first_grade2_rank"])
                else:
                    k = int(key.rsplit("_", 1)[1])
                    total += Fraction(len(relevant.intersection(ranked[:k])), len(relevant))
            value = total / len(eligible)
            exact[key] = f"{value.numerator}/{value.denominator}"
        output[variant] = {"description": VARIANTS[variant], "per_query": per_query,
                           "macro_average": macro, "macro_exact_fraction": exact}
    return output


def _read_only_engine(database_url: str):
    import re

    from sqlalchemy import create_engine, event

    engine = create_engine(database_url, pool_pre_ping=True,
                           connect_args={"options": "-c default_transaction_read_only=on"})

    @event.listens_for(engine, "before_cursor_execute")
    def reject_writes(conn, cursor, statement, parameters, context, executemany):
        if not re.match(r"(?i)^\s*(SELECT|SHOW|SET|BEGIN|ROLLBACK|COMMIT)\b", statement):
            raise RuntimeError("compare-matching is read-only; a write was attempted")

    return engine


def compare_matching(candidates_path: Path, jobs_path: Path, judgments_path: Path, mapping_path: Path,
                     database_url: str, destination: Path, policy_path: Path | None = None,
                     template_version: str | None = None) -> dict:
    """Rank the benchmark jobs with variants A-D from the live database (read-only) and score them.

    Writes `<destination>/rankings-<variant>.jsonl` (the Phase 5 ranking format, so variant A
    can be passed to `evaluate`) and `<destination>/matching-comparison.json`. Refuses to
    overwrite existing files.
    """
    from sqlalchemy.orm import Session

    from app.db.models import CandidateProfile, User
    from app.services.matching_service import MatchingService
    from app.services.retrieval_service import RetrievalService

    template_version = resolve_template(template_version)
    candidates, jobs = load_corpus(candidates_path, jobs_path)
    judgments = load_judgments(judgments_path, candidates, jobs, policy_path=policy_path,
                               candidates_path=candidates_path, jobs_path=jobs_path)
    policy = _bound_policy(policy_path, candidates_path, jobs_path, judgments_path, candidates, jobs, judgments)
    coverage = query_coverage(candidates, judgments, policy)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if set(mapping.get("candidates", {})) != set(candidates) or set(mapping.get("jobs", {})) != set(jobs):
        raise ValueError("Evaluation-to-database mapping is incomplete or has unknown IDs")
    user_ids = {alias: UUID(value) for alias, value in mapping["candidates"].items()}
    job_ids = {alias: UUID(value) for alias, value in mapping["jobs"].items()}
    if len(set(user_ids.values())) != len(user_ids) or len(set(job_ids.values())) != len(job_ids):
        raise ValueError("Evaluation mapping contains duplicate database IDs")
    alias_by_job = {value: key for key, value in job_ids.items()}
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    targets = [destination / f"rankings-{variant}.jsonl" for variant in VARIANTS]
    targets.append(destination / "matching-comparison.json")
    if any(path.exists() for path in targets):
        raise FileExistsError(f"Refusing to overwrite outputs in {destination}")

    rankings: dict[str, dict[str, list[str]]] = {variant: {} for variant in VARIANTS}
    engine = _read_only_engine(database_url)
    try:
        with Session(engine) as db:
            matching = MatchingService(db)
            job_items = {alias: matching._job_items(job_id) for alias, job_id in job_ids.items()}
            retrieval = RetrievalService(db, template_version)
            for alias in sorted(candidates):
                user = db.get(User, user_ids[alias])
                if user is None or user.status != "active" or not any(r.name == "candidate" for r in user.roles):
                    raise ValueError(f"Mapped user for {alias} is not an active candidate")
                profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).one()
                rows = retrieval.jobs_for_user(user, 1000, sources={EVALUATION_SOURCE})  # D056
                similarity = {alias_by_job[row["job_id"]]: row["retrieval_similarity"]
                              for row in rows if row["job_id"] in alias_by_job}
                if set(similarity) != set(jobs):
                    raise ValueError(f"Retrieval did not return every benchmark job for {alias}; index first")
                # A keeps the service order (distance, then job ID); other jobs are dropped without reordering.
                rankings["A"][alias] = [alias_by_job[row["job_id"]] for row in rows if row["job_id"] in alias_by_job]
                candidate_items = matching._candidate_items(profile.id)
                rankings["B"][alias] = coverage_order(candidate_items, job_items, job_ids, use_concepts=False)
                rankings["C"][alias] = coverage_order(candidate_items, job_items, job_ids)
                rankings["D"][alias] = coverage_order(candidate_items, job_items, job_ids, similarity=similarity)
            db.rollback()
    finally:
        engine.dispose()

    corpus = {"candidates": _sha256(candidates_path), "jobs": _sha256(jobs_path)}
    for variant, by_candidate in rankings.items():
        if any(len(ids) != len(jobs) or set(ids) != set(jobs) for ids in by_candidate.values()):
            raise ValueError(f"Variant {variant} did not rank every benchmark job exactly once")
        path = destination / f"rankings-{variant}.jsonl"
        path.write_text("".join(json.dumps({"candidate_id": alias, "retrieved_job_ids": ids, "variant": variant,
                                            "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
                                            "template_version": template_version, "corpus_sha256": corpus},
                                           sort_keys=True) + "\n" for alias, ids in sorted(by_candidate.items())),
                        encoding="utf-8")
        path.chmod(0o600)
    eligible = list(coverage["eligible_candidate_ids"])
    result = {
        "variants": score_rankings(rankings, judgments, eligible),
        "query_coverage": coverage,
        "evaluable_queries": eligible,
        "metric_definitions": {
            "recall_at_k": "grade-2 jobs in the top k / all grade-2 jobs of the query (Phase 5)",
            "mrr": "1 / rank of the first grade-2 job (Phase 5)",
            "ndcg_at_10": "gain 2^grade - 1 over grades 0/1/2, discount log2(rank + 1), "
                          "ideal = all 30 judged jobs sorted by grade",
            "macro": "unweighted mean over the evaluable queries",
        },
        "limitations": NO_SIGNIFICANCE,
        "data_sha256": {**corpus, "judgments": _sha256(judgments_path),
                        **({"evaluation_policy": _sha256(policy_path)} if policy_path else {}),
                        **{f"rankings_{v}": _sha256(destination / f"rankings-{v}.jsonl") for v in VARIANTS}},
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "template_version": template_version},
    }
    output = destination / "matching-comparison.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output.chmod(0o600)
    return {variant: {"macro_average": data["macro_average"], "macro_exact_fraction": data["macro_exact_fraction"]}
            for variant, data in result["variants"].items()}
