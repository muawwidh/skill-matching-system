"""Job source commands: `python -m app.job_sources.cli <command>`."""
import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.db.session import SessionLocal
from app.job_sources.greenhouse import GreenhouseAdapter
from app.job_sources.http import HttpJsonClient
from app.job_sources.evaluation import mark_evaluation_jobs, evaluation_job_ids
from app.retrieval.auto_reindex import DISABLED_KEY


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.job_sources.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    mark = commands.add_parser("mark-evaluation-jobs", help="Tag the mapped evaluation jobs as source=evaluation.")
    mark.add_argument("--mapping", type=Path, required=True, help="Evaluation-to-database mapping JSON.")
    mark.add_argument("--dry-run", action="store_true")
    verify = commands.add_parser("verify-sources", help="Call each configured Greenhouse board and report job counts.")
    verify.add_argument("--boards", help="Comma-separated tokens to check instead of GREENHOUSE_BOARDS.")
    commands.add_parser("import-live-jobs", help="Fetch, filter, dedupe and process live jobs; archive stale ones.")
    sample = commands.add_parser("sample-extraction",
                                 help="Read-only: write a seeded labelling sample of live jobs' extracted skills.")
    sample.add_argument("--out", type=Path, required=True,
                        help="New directory, e.g. evaluation/local/live-extraction-sample-<date> (git-ignored).")
    sample.add_argument("--size", type=int, default=20)
    sample.add_argument("--seed", type=int, default=20261121)
    score = commands.add_parser("score-extraction",
                                help="Precision and missed required skills from a labelled labels.csv.")
    score.add_argument("--labels", type=Path, required=True)
    score.add_argument("--gaps", type=Path, help="Error log: missed required skills and tools come from it.")
    args = parser.parse_args(argv)

    if args.command == "sample-extraction":
        from app.job_sources.extraction_sample import sample as write_sample

        with SessionLocal(info={DISABLED_KEY: True}) as db:
            result = write_sample(db, args.out, args.size, args.seed)
        print(json.dumps({"directory": str(result.directory), "population": result.population,
                          "jobs": len(result.job_ids), "skill_rows": result.skill_rows, "seed": args.seed},
                         sort_keys=True))
        return 0

    if args.command == "score-extraction":
        from app.job_sources.extraction_sample import score as score_labels

        print(json.dumps(score_labels(args.labels, args.gaps), indent=2, sort_keys=True))
        return 0

    if args.command == "import-live-jobs":
        from app.job_sources.registry import build_adapters
        from app.services.job_import_service import JobImportService

        client = HttpJsonClient(settings.JOB_SOURCE_USER_AGENT, settings.JOB_SOURCE_MIN_INTERVAL_SECONDS)
        with SessionLocal() as db:
            report = JobImportService(db, build_adapters(settings), client).run()
        print(json.dumps(report, sort_keys=True, default=str))
        return 0

    if args.command == "verify-sources":
        boards = [b.strip() for b in args.boards.split(",") if b.strip()] if args.boards else settings.greenhouse_boards
        client = HttpJsonClient(settings.JOB_SOURCE_USER_AGENT, settings.JOB_SOURCE_MIN_INTERVAL_SECONDS)
        result = GreenhouseAdapter(boards).verify(client)
        print(json.dumps({"boards": result, "working": sorted(b for b, v in result.items() if isinstance(v, int) and v > 0),
                          "failing": sorted(b for b, v in result.items() if not (isinstance(v, int) and v > 0))},
                         sort_keys=True))
        return 0

    if args.command == "mark-evaluation-jobs":
        with SessionLocal(info={DISABLED_KEY: True}) as db:
            result = mark_evaluation_jobs(db, evaluation_job_ids(args.mapping))
            if args.dry_run:
                db.rollback()
            else:
                db.commit()
        print(json.dumps({**result, "dry_run": args.dry_run}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
