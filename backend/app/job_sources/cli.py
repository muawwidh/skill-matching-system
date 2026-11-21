"""Job source commands: `python -m app.job_sources.cli <command>` (D052)."""
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
    args = parser.parse_args(argv)

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
