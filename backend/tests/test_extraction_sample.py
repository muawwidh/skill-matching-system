"""Live-job extraction labelling sample: seeded, read-only, never overwrites; scoring of labels."""
import csv
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.db.models import Job, JobSkill, ProcessingLog
from app.job_sources import cli
from app.job_sources.extraction_sample import COLUMNS, GAP_COLUMNS, sample, score


def _jobs(db):
    ids = {}
    for n in range(8):
        for source in ("arbeitnow", "greenhouse"):
            job = Job(title=f"{source} role {n}", company="Acme", location="Berlin", description=f"Need Python {n}",
                      cleaned_description=f"Need Python {n}", status="processed", source=source,
                      external_id=f"{source}-{n}", external_url=f"https://example.com/{source}/{n}",
                      posted_at=datetime(2026, 11, n + 1, tzinfo=timezone.utc))
            db.add(job)
            db.flush()
            for text, kind, requirement, status in (("python", "skill", "required", "pending"),
                                                    ("python", "skill", "preferred", "pending"),
                                                    ("sql", "skill", "preferred", "approved"),
                                                    ("excel", "tool", "unknown", "rejected")):
                db.add(JobSkill(job_id=job.id, raw_text=text, normalized_text=text, skill_type=kind,
                                requirement_type=requirement, review_status=status, source="extraction",
                                evidence_sentence=f"We use {text}."))
            db.add(JobSkill(job_id=job.id, raw_text="Go", normalized_text="go", skill_type="skill",
                            requirement_type="required", review_status="approved", source="manual"))
            ids[(source, n)] = job.id
    for source, status in (("manual", "processed"), ("evaluation", "processed"), ("arbeitnow", "archived")):
        db.add(Job(title=f"{source} {status}", description="x", cleaned_description="x", status=status,
                   source=source, external_id="z" if source == "arbeitnow" else None))
    db.commit()
    return ids


def _counts(db):
    return tuple(db.scalar(select(func.count()).select_from(model)) for model in (Job, JobSkill, ProcessingLog))


def test_sample_is_seeded_read_only_and_only_live_active_jobs(db_session, tmp_path):
    ids = _jobs(db_session)
    before = _counts(db_session)
    first = sample(db_session, tmp_path / "a", size=5, seed=7)
    again = sample(db_session, tmp_path / "b", size=5, seed=7)
    other = sample(db_session, tmp_path / "c", size=5, seed=8)
    assert first.job_ids == again.job_ids and first.job_ids != other.job_ids
    assert first.population == 16 and set(first.job_ids) <= set(ids.values())
    assert _counts(db_session) == before  # nothing written to the database

    rows = list(csv.DictReader((tmp_path / "a" / "labels.csv").open(encoding="utf-8")))
    assert list(rows[0]) == COLUMNS
    assert [r["row_type"] for r in rows] == ["job", "skill", "skill"] * 5
    python = rows[1]  # distinct skills only: two python occurrences grouped, strongest requirement
    assert (python["skill"], python["occurrences"], python["requirement"], python["status"]) == (
        "python", "2", "required", "automatic")
    assert rows[2]["skill"] == "sql" and rows[2]["status"] == "approved"
    assert not {r["skill"] for r in rows} & {"excel", "go"}  # rejected and manually added skills left out
    assert all(r["label"] == "" and r["missed_required_skills"] == "" for r in rows)
    manifest = json.loads((tmp_path / "a" / "manifest.json").read_text())
    assert manifest["seed"] == 7 and manifest["job_ids"] == [str(i) for i in first.job_ids]
    assert manifest["skill_rows"] == 10 and set(manifest["sha256"]) == {"labels.csv", "postings.md", "gaps.csv"}
    assert (tmp_path / "a" / "gaps.csv").read_text().splitlines() == [",".join(GAP_COLUMNS)]
    assert manifest["gaps_allowed_values"]["type"] == ["missed", "false_positive", "wrong_mapping"]
    assert "Need Python" in (tmp_path / "a" / "postings.md").read_text()


def test_sample_never_overwrites_labels_and_needs_enough_jobs(db_session, tmp_path):
    _jobs(db_session)
    sample(db_session, tmp_path / "a", size=2, seed=1)
    with pytest.raises(FileExistsError):
        sample(db_session, tmp_path / "a", size=2, seed=1)
    with pytest.raises(ValueError, match="Only 16"):
        sample(db_session, tmp_path / "big", size=17)


def _write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in COLUMNS})


def test_score_precision_and_missed_required(tmp_path):
    labels = tmp_path / "labels.csv"
    skill = lambda label, kind="skill", status="automatic", req="required": {  # noqa: E731
        "row_type": "skill", "label": label, "skill_type": kind, "status": status, "requirement": req}
    _write(labels, [
        {"row_type": "job", "missed_required_skills": "Kubernetes; terraform\nKubernetes"},
        skill("correct"), skill("Incorrect", "tool"), skill("c", status="approved"),
        {"row_type": "job", "missed_required_skills": "none"},
        skill("correct", req="preferred"), skill(""),
        {"row_type": "job", "missed_required_skills": ""},
        skill("incorrect"),
    ])
    result = score(labels)
    assert (result["correct"], result["incorrect"], result["labelled"], result["precision"]) == (3, 2, 5, 0.6)
    assert result["unlabelled_skill_rows"] == 1 and result["jobs"] == 3 and result["skill_rows"] == 6
    assert result["by"]["skill_type"]["tool"]["precision"] == 0.0
    assert result["by"]["status"]["approved"] == {"correct": 1, "incorrect": 0, "labelled": 1, "precision": 1.0}
    # Kubernetes counted once per job; "none" is a labelled job with 0 missed; blank is unlabelled.
    assert result["missed_required"] == {"jobs_labelled": 2, "jobs_unlabelled": 1, "total": 2,
                                         "jobs_with_any": 1, "mean_per_job": 1.0}


def test_score_rejects_unknown_labels(tmp_path):
    labels = tmp_path / "labels.csv"
    _write(labels, [{"row_type": "job"}, {"row_type": "skill", "label": "maybe"}])
    with pytest.raises(ValueError, match="line 3: 'maybe'"):
        score(labels)


def test_cli_scores_a_labels_file(tmp_path, capsys):
    labels = tmp_path / "labels.csv"
    _write(labels, [{"row_type": "job", "missed_required_skills": "none"}, {"row_type": "skill", "label": "correct"}])
    assert cli.main(["score-extraction", "--labels", str(labels)]) == 0
    assert json.loads(capsys.readouterr().out)["precision"] == 1.0
