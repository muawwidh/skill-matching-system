import argparse
import json
from pathlib import Path
from time import perf_counter
from uuid import UUID

from sqlalchemy import select

from app.db.models import CandidateProfile, Job
from app.db.session import SessionLocal
from app.retrieval.embedder import default_embedder
from app.retrieval.benchmark import (cohens_kappa, evaluate_pack, export_rankings,
                                     load_corpus, load_judgments, write_blind_export)
from app.retrieval.representation import MODEL_ID, MODEL_REVISION


def provision(path: str) -> None:
    from huggingface_hub import snapshot_download
    location = Path(path)
    if location.exists() and any(location.iterdir()):
        raise RuntimeError("Model directory is not empty; refusing to overwrite it.")
    location.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=MODEL_ID, revision=MODEL_REVISION, local_dir=location,
                      allow_patterns=["*.json", "*.txt", "*.model", "*.safetensors"],
                      ignore_patterns=["onnx/*", "openvino/*", ".eval_results/*", "pytorch_model.bin"])
    (location / "revision.txt").write_text(MODEL_REVISION + "\n")
    print(json.dumps({"model": MODEL_ID, "revision": MODEL_REVISION, "path": str(location)}))


def index(kind: str, limit: int, after: str | None) -> None:
    embedder = default_embedder()
    cls = Job if kind == "jobs" else CandidateProfile
    cursor = UUID(after) if after else None
    counts = {"indexed": 0, "unchanged": 0, "not_ready": 0, "failed": 0}
    failures = []
    started = perf_counter()
    with SessionLocal() as db:
        statement = select(cls.id).order_by(cls.id).limit(limit)
        if cursor:
            statement = statement.where(cls.id > cursor)
        ids = list(db.scalars(statement))
    resume_after = cursor
    for item_id in ids:
        try:
            with SessionLocal() as db:
                service = RetrievalService(db)
                outcome = service.index_job(item_id, embedder) if kind == "jobs" else service.index_profile(item_id, embedder)
                db.commit()
            counts[outcome.outcome] += 1
        except Exception as exc:
            counts["failed"] += 1
            failures.append(str(item_id))
            from app.repositories.retrieval_repository import RetrievalRepository
            with SessionLocal() as db:
                RetrievalRepository(db).mark_failed(item_id, "job" if kind == "jobs" else "profile")
                db.commit()
            print(json.dumps({"id": str(item_id), "error": str(exc)}))
        if not failures:
            resume_after = item_id
    print(json.dumps({"kind": kind, "processed": len(ids), "counts": counts,
                      "next_after": str(resume_after) if resume_after else None,
                      "failed_ids": failures,
                      "duration_seconds": round(perf_counter() - started, 3)}))


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Phase 5 retrieval operations")
    sub = parser.add_subparsers(dest="command", required=True)
    download = sub.add_parser("provision-model")
    download.add_argument("--path", default="../models/multilingual-e5-small-fd1525a")
    indexing = sub.add_parser("index")
    indexing.add_argument("kind", choices=("jobs", "profiles"))
    indexing.add_argument("--limit", type=int, default=100)
    indexing.add_argument("--after")
    blind = sub.add_parser("blind-export", help="Create randomized, score-free labelling CSV")
    blind.add_argument("candidates", type=Path)
    blind.add_argument("jobs", type=Path)
    blind.add_argument("output", type=Path)
    blind.add_argument("--seed", type=int, default=20261002)
    validate = sub.add_parser("validate-benchmark")
    validate.add_argument("candidates", type=Path)
    validate.add_argument("jobs", type=Path)
    validate.add_argument("--judgments", type=Path)
    rankings = sub.add_parser("export-rankings", help="Only from isolated phase5_verify")
    rankings.add_argument("candidates", type=Path)
    rankings.add_argument("jobs", type=Path)
    rankings.add_argument("mapping", type=Path)
    rankings.add_argument("output", type=Path)
    rankings.add_argument("--database-url", required=True)
    evaluation = sub.add_parser("evaluate", help="Require complete, validated human judgments")
    evaluation.add_argument("candidates", type=Path)
    evaluation.add_argument("jobs", type=Path)
    evaluation.add_argument("judgments", type=Path)
    evaluation.add_argument("rankings", type=Path)
    evaluation.add_argument("--grade-one-exploratory", action="store_true")
    kappa = sub.add_parser("kappa", help="Optional second-reviewer agreement")
    kappa.add_argument("candidates", type=Path)
    kappa.add_argument("jobs", type=Path)
    kappa.add_argument("first", type=Path)
    kappa.add_argument("second", type=Path)
    smoke = sub.add_parser("smoke-model")
    args = parser.parse_args()
    if args.command == "provision-model":
        provision(args.path)
    elif args.command == "index":
        if not 1 <= args.limit <= 1000:
            parser.error("--limit must be between 1 and 1000")
        index(args.kind, args.limit, args.after)
    elif args.command == "evaluate":
        print(json.dumps(evaluate_pack(args.candidates, args.jobs, args.judgments,
                                       args.rankings, args.grade_one_exploratory), sort_keys=True))
    elif args.command == "blind-export":
        candidates, jobs = load_corpus(args.candidates, args.jobs)
        metadata = write_blind_export(candidates, jobs, args.output, args.seed)
        print(json.dumps(metadata, sort_keys=True))
    elif args.command == "validate-benchmark":
        candidates, jobs = load_corpus(args.candidates, args.jobs)
        result = {"candidates": len(candidates), "jobs": len(jobs), "expected_pairs": len(candidates) * len(jobs)}
        if args.judgments:
            result["judged_pairs"] = len(load_judgments(args.judgments, candidates, jobs))
        print(json.dumps(result, sort_keys=True))
    elif args.command == "export-rankings":
        print(json.dumps(export_rankings(args.candidates, args.jobs, args.mapping,
                                         args.database_url, args.output), sort_keys=True))
    elif args.command == "kappa":
        candidates, jobs = load_corpus(args.candidates, args.jobs)
        print(json.dumps(cohens_kappa(args.first, args.second, candidates, jobs), sort_keys=True))
    else:
        model = default_embedder()
        print(json.dumps({"model": MODEL_ID, "revision": MODEL_REVISION,
                          "dimension": len(model.encode("query: Python developer"))}))


if __name__ == "__main__":
    main()
