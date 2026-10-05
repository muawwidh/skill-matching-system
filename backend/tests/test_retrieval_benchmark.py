"""Synthetic data only: validates evaluation tooling, not retrieval quality."""

import csv
import json
from pathlib import Path

import pytest

from app.retrieval.benchmark import (cohens_kappa, evaluate_pack, load_corpus,
                                     load_judgments, pair_order, write_blind_export,
                                     export_rankings)
from app.retrieval.representation import MODEL_ID, MODEL_REVISION, TEMPLATE_VERSION


def _files(tmp_path: Path, job_count: int = 3):
    candidates = tmp_path / "candidates.jsonl"
    jobs = tmp_path / "jobs.jsonl"
    candidate_rows = [dict(id=f"candidate_{i}", language="en", profile_summary="Synthetic profile",
                           approved_skills=["Python"], approved_evidence_paraphrases=[],
                           canonical_taxonomy=[], source_category="synthetic_test",
                           consent_or_redistribution_status="author_paraphrase",
                           deidentification_notes="No person exists") for i in range(2)]
    job_rows = [dict(id=f"job_{i:02}", language="en", title="Synthetic role", employer_label="Test employer",
                     region_country="Test region", employment_type="full-time",
                     required_skills=["Python"], preferred_skills=[],
                     description_paraphrase="Synthetic test job", source_category="author_constructed",
                     access_date="2026-10-02", redistribution_status="author_paraphrase",
                     deidentification_notes="No source person or employer") for i in range(job_count)]
    candidates.write_text("".join(json.dumps(row) + "\n" for row in candidate_rows))
    jobs.write_text("".join(json.dumps(row) + "\n" for row in job_rows))
    return candidates, jobs, candidate_rows, job_rows


def _judgments(path, candidates, jobs, relevant_job="job_00"):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "job_id", "relevance_grade",
                                                    "reviewer_id", "judgment_date", "rationale", "uncertainty_flag"])
        writer.writeheader()
        for candidate in candidates:
            for job in jobs:
                writer.writerow(dict(candidate_id=candidate["id"], job_id=job["id"],
                                     relevance_grade=2 if job["id"] == relevant_job else 0,
                                     reviewer_id="reviewer-a", judgment_date="2026-10-02",
                                     rationale="Synthetic arithmetic fixture", uncertainty_flag="false"))


def test_blind_export_complete_reproducible_and_no_scores(tmp_path):
    candidates_path, jobs_path, _, _ = _files(tmp_path)
    candidates, jobs = load_corpus(candidates_path, jobs_path)
    assert pair_order(candidates, jobs) == pair_order(candidates, jobs)
    output = tmp_path / "blind.csv"
    metadata = write_blind_export(candidates, jobs, output)
    assert metadata["pair_count"] == 6
    assert json.loads((tmp_path / "blind.csv.metadata.json").read_text())["seed"] == 20261002
    assert "similarity" not in output.read_text() and "score" not in output.read_text()
    assert len(list(csv.DictReader(output.open()))) == 6
    with pytest.raises(FileExistsError):
        write_blind_export(candidates, jobs, output)


def test_corpus_rejects_missing_provenance_pii_duplicate_and_empty_skills(tmp_path):
    candidates, jobs, candidate_rows, _ = _files(tmp_path)
    candidate_rows[0]["profile_summary"] = "contact me at person@example.com"
    candidates.write_text("".join(json.dumps(row) + "\n" for row in candidate_rows))
    with pytest.raises(ValueError, match="personal identifier"):
        load_corpus(candidates, jobs)
    candidate_rows[0]["profile_summary"] = "Synthetic profile"
    candidate_rows[0]["consent_or_redistribution_status"] = "TBD"
    candidates.write_text("".join(json.dumps(row) + "\n" for row in candidate_rows))
    with pytest.raises(ValueError, match="missing or placeholder"):
        load_corpus(candidates, jobs)
    candidate_rows[0]["consent_or_redistribution_status"] = "author_paraphrase"
    candidate_rows[1]["id"] = candidate_rows[0]["id"]
    candidates.write_text("".join(json.dumps(row) + "\n" for row in candidate_rows))
    with pytest.raises(ValueError, match="duplicate ID"):
        load_corpus(candidates, jobs)
    candidate_rows[1]["id"] = "candidate_1"
    candidate_rows[0]["approved_skills"] = []
    candidates.write_text("".join(json.dumps(row) + "\n" for row in candidate_rows))
    with pytest.raises(ValueError, match="no approved skills"):
        load_corpus(candidates, jobs)


def test_job_rejects_missing_provenance_source_url_and_empty_skills(tmp_path):
    candidate_path, job_path, _, job_rows = _files(tmp_path)
    job_rows[0]["language"] = "de"
    job_path.write_text("".join(json.dumps(row) + "\n" for row in job_rows))
    with pytest.raises(ValueError, match="language en only"):
        load_corpus(candidate_path, job_path)
    job_rows[0]["language"] = "en"
    job_rows[0]["redistribution_status"] = "TBD"
    job_path.write_text("".join(json.dumps(row) + "\n" for row in job_rows))
    with pytest.raises(ValueError, match="missing or placeholder"):
        load_corpus(candidate_path, job_path)
    job_rows[0]["redistribution_status"] = "author_paraphrase"
    job_rows[0]["source_category"] = "public_posting"
    job_path.write_text("".join(json.dumps(row) + "\n" for row in job_rows))
    with pytest.raises(ValueError, match="requires source URL"):
        load_corpus(candidate_path, job_path)
    job_rows[0]["source_category"] = "author_constructed"
    job_rows[0]["required_skills"] = []
    job_path.write_text("".join(json.dumps(row) + "\n" for row in job_rows))
    with pytest.raises(ValueError, match="no skill content"):
        load_corpus(candidate_path, job_path)


def test_judgment_matrix_rejects_missing_unknown_duplicate_invalid_and_no_positive(tmp_path):
    candidate_path, job_path, candidate_rows, job_rows = _files(tmp_path)
    candidates, jobs = load_corpus(candidate_path, job_path)
    path = tmp_path / "judgments.csv"
    _judgments(path, candidate_rows, job_rows)
    assert len(load_judgments(path, candidates, jobs)) == 6
    original = path.read_text()
    path.write_text("\n".join(original.splitlines()[:-1]) + "\n")
    with pytest.raises(ValueError, match="Missing 1"):
        load_judgments(path, candidates, jobs)
    path.write_text(original + original.splitlines()[-1] + "\n")
    with pytest.raises(ValueError, match="duplicate pair"):
        load_judgments(path, candidates, jobs)
    path.write_text(original.replace("job_01", "unknown"))
    with pytest.raises(ValueError, match="unknown"):
        load_judgments(path, candidates, jobs)
    path.write_text(original.replace(",2,reviewer", ",3,reviewer"))
    with pytest.raises(ValueError, match="invalid or missing grade"):
        load_judgments(path, candidates, jobs)
    path.write_text(original.replace(",2,reviewer", ",0,reviewer"))
    with pytest.raises(ValueError, match="no grade-2"):
        load_judgments(path, candidates, jobs)


def test_synthetic_metrics_checksums_provenance_and_grade_one_separation(tmp_path):
    candidate_path, job_path, candidate_rows, job_rows = _files(tmp_path, 21)
    judgments = tmp_path / "judgments.csv"
    _judgments(judgments, candidate_rows, job_rows)
    rankings = tmp_path / "rankings.jsonl"
    import hashlib
    hashes = {"candidates": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
              "jobs": hashlib.sha256(job_path.read_bytes()).hexdigest()}
    rows = []
    for candidate in candidate_rows:
        ids = [job["id"] for job in job_rows]
        rows.append(dict(candidate_id=candidate["id"], retrieved_job_ids=ids,
                         model_id=MODEL_ID, model_revision=MODEL_REVISION,
                         template_version=TEMPLATE_VERSION, corpus_sha256=hashes))
    rankings.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="requires 8 candidates"):
        evaluate_pack(candidate_path, job_path, judgments, rankings)
    result = evaluate_pack(candidate_path, job_path, judgments, rankings, allow_synthetic=True)
    assert result["corpus"] == {"candidates": 2, "jobs": 21, "judgments": 42,
                                "grade_2_relevant": 2, "grade_1_partial": 0}
    assert result["macro_average"] == {"recall_at_5": 1, "recall_at_10": 1,
                                        "recall_at_20": 1, "mrr": 1}
    assert "exploratory_grade_1_or_2" not in result
    judgment_rows = list(csv.DictReader(judgments.open()))
    for row in judgment_rows:
        if row["job_id"] == "job_01":
            row["relevance_grade"] = "1"
    with judgments.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=judgment_rows[0])
        writer.writeheader()
        writer.writerows(judgment_rows)
    exploratory = evaluate_pack(candidate_path, job_path, judgments, rankings,
                                grade_one=True, allow_synthetic=True)
    assert exploratory["corpus"]["grade_1_partial"] == 2
    assert exploratory["macro_average"]["recall_at_5"] == 1
    assert exploratory["exploratory_grade_1_or_2"]["recall_at_5"] == 1
    rows[0]["corpus_sha256"] = {**hashes, "jobs": "wrong"}
    rankings.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="checksum mismatch"):
        evaluate_pack(candidate_path, job_path, judgments, rankings, allow_synthetic=True)
    rows[0]["corpus_sha256"] = hashes.copy()
    rows[0]["model_revision"] = "incorrect"
    rankings.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="provenance mismatch"):
        evaluate_pack(candidate_path, job_path, judgments, rankings, allow_synthetic=True)
    rows[0]["model_revision"] = MODEL_REVISION
    rows[0]["retrieved_job_ids"] = rows[0]["retrieved_job_ids"][:-1]
    rankings.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="every benchmark job"):
        evaluate_pack(candidate_path, job_path, judgments, rankings, allow_synthetic=True)


def test_optional_kappa_on_identical_synthetic_reviewers(tmp_path):
    candidate_path, job_path, candidate_rows, job_rows = _files(tmp_path)
    candidates, jobs = load_corpus(candidate_path, job_path)
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    _judgments(first, candidate_rows, job_rows)
    second.write_text(first.read_text().replace("reviewer-a", "reviewer-b"))
    assert cohens_kappa(first, second, candidates, jobs)["cohens_kappa"] == 1
    second.write_bytes(first.read_bytes())
    with pytest.raises(ValueError, match="must differ"):
        cohens_kappa(first, second, candidates, jobs)


def test_export_rankings_rejects_nonisolated_database_before_connecting(tmp_path):
    candidates, jobs, _, _ = _files(tmp_path)
    with pytest.raises(ValueError, match="isolated phase5_verify"):
        export_rankings(candidates, jobs, tmp_path / "absent.json", "postgresql://localhost/developer",
                        tmp_path / "rankings.jsonl")
