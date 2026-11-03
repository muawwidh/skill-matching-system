"""Synthetic tooling fixtures and a gated read-only private-corpus check; no quality claims."""

import csv
import hashlib
import json
import os
from pathlib import Path
import stat

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


def _restricted_job(row):
    row.pop("description_paraphrase")
    row.update(description_text="Synthetic source duties and qualifications.", content_mode="verbatim_restricted",
               redistribution_status="restricted_internal_use", redistribution_allowed=False,
               source_category="public_posting", source_id="S01", pdf_filename="S01.pdf",
               source_url="https://careers.example.org/jobs/12345678901?source=public",
               accessed_at="2026-11-03T12:00:00+00:00", access_date="2026-11-03", pdf_sha256="a" * 64)
    row["normalized_text_sha256"] = hashlib.sha256(row["description_text"].encode()).hexdigest()
    return row


def _write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_restricted_verbatim_source_and_private_blind_export(tmp_path):
    cp, jp, _, rows = _files(tmp_path, 1)
    _restricted_job(rows[0])
    _write_rows(jp, rows)
    candidates, jobs = load_corpus(cp, jp)
    assert jobs["job_00"]["description_text"] == rows[0]["description_text"]
    assert "description_paraphrase" not in jobs["job_00"]
    output = tmp_path / "blind.csv"
    metadata = write_blind_export(candidates, jobs, output)
    exported = list(csv.DictReader(output.open()))
    assert {r["job_content_mode"] for r in exported} == {"verbatim_restricted"}
    assert {r["job_redistribution_status"] for r in exported} == {"restricted_internal_use"}
    assert {r["job_redistribution_allowed"] for r in exported} == {"False"}
    assert metadata["contains_restricted_verbatim"] and metadata["redistribution_allowed"] is False
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "blind.csv.metadata.json").stat().st_mode) == 0o600
    jobs["job_00"]["redistribution_allowed"] = True
    with pytest.raises(ValueError, match="redistribution_allowed=false"):
        write_blind_export(candidates, jobs, tmp_path / "bad.csv")
    assert not (tmp_path / "bad.csv").exists()


@pytest.mark.parametrize("flag", [True, None, "false", 0])
def test_restricted_verbatim_requires_explicit_false_flag(tmp_path, flag):
    cp, jp, _, rows = _files(tmp_path, 1)
    _restricted_job(rows[0])["redistribution_allowed"] = flag
    _write_rows(jp, rows)
    with pytest.raises(ValueError, match="redistribution_allowed=false"):
        load_corpus(cp, jp)


@pytest.mark.parametrize("field", ["source_id", "source_url", "accessed_at", "pdf_filename", "pdf_sha256", "normalized_text_sha256"])
def test_restricted_verbatim_requires_complete_provenance(tmp_path, field):
    cp, jp, _, rows = _files(tmp_path, 1)
    _restricted_job(rows[0]).pop(field)
    _write_rows(jp, rows)
    with pytest.raises(ValueError, match=field):
        load_corpus(cp, jp)


@pytest.mark.parametrize("field,value,error", [
    ("normalized_text_sha256", "b" * 64, "checksum mismatch"),
    ("pdf_sha256", "TBD", "placeholder"),
    ("pdf_filename", "../S01.pdf", "basename"),
    ("accessed_at", "2026-11-03T12:00:00", "UTC"),
    ("accessed_at", "2026-11-02T12:00:00Z", "access_date"),
    ("source_category", "author_constructed", "job-source provenance"),
    ("source_url", "https://", "source URL"),
    ("redistribution_status", "redistributable", "restricted_internal_use"),
    ("content_mode", "paraphrased", "redistribution status"),
    ("content_mode", "TBD", "content_mode"),
])
def test_restricted_verbatim_rejects_invalid_contract(tmp_path, field, value, error):
    cp, jp, _, rows = _files(tmp_path, 1)
    _restricted_job(rows[0])[field] = value
    _write_rows(jp, rows)
    with pytest.raises(ValueError, match=error):
        load_corpus(cp, jp)


def test_restricted_job_rule_does_not_extend_candidate_consent(tmp_path):
    cp, jp, candidates, _ = _files(tmp_path)
    candidates[0].update(consent_or_redistribution_status="restricted_internal_use",
                         redistribution_allowed=False, content_mode="verbatim_restricted")
    _write_rows(cp, candidates)
    with pytest.raises(ValueError, match="candidate .*consent/redistribution"):
        load_corpus(cp, jp)


def test_paraphrased_legacy_and_modern_records_are_compatible(tmp_path):
    cp, jp, _, rows = _files(tmp_path, 2)
    rows[1]["description_text"] = rows[1].pop("description_paraphrase")
    rows[1]["content_mode"] = "paraphrased"
    _write_rows(jp, rows)
    _, jobs = load_corpus(cp, jp)
    assert all(job["content_mode"] == "paraphrased" for job in jobs.values())
    assert jobs["job_00"]["description_text"] == rows[0]["description_paraphrase"]
    rows[1]["description_paraphrase"] = "Conflicting text"
    _write_rows(jp, rows)
    with pytest.raises(ValueError, match="conflicting description"):
        load_corpus(cp, jp)


def test_job_template_stays_deliberately_incomplete_and_can_be_filled(tmp_path):
    cp, jp, _, _ = _files(tmp_path, 1)
    repository = Path(__file__).resolve().parents[2]
    template = json.loads((repository / "evaluation/templates/jobs.template.jsonl").read_text())
    _write_rows(jp, [template])
    with pytest.raises(ValueError, match="placeholder"):
        load_corpus(cp, jp)
    template.update(id="template_job", language="en", title="Synthetic role", employer_label="Synthetic employer",
                    region_country="Test region", employment_type="full-time", required_skills=["Python"],
                    description_text="Synthetic author-written paraphrase", source_category="author_constructed",
                    access_date="2026-11-03", redistribution_status="author_paraphrase",
                    deidentification_notes="Synthetic fixture only")
    _write_rows(jp, [template])
    assert load_corpus(cp, jp)[1]["template_job"]["content_mode"] == "paraphrased"


@pytest.mark.parametrize("field", ["required_skills", "preferred_skills"])
def test_job_skill_contact_guard_is_unchanged(tmp_path, field):
    cp, jp, _, rows = _files(tmp_path, 1)
    rows[0][field] = ["Email test@example.org"]
    _write_rows(jp, rows)
    with pytest.raises(ValueError, match="personal identifier"):
        load_corpus(cp, jp)


@pytest.mark.parametrize("content", ["Email test@example.org", "Call +45 12345678", "Recruiter: Test contact", "Updated 31.02.2026"])
def test_job_contact_guard_remains_active(tmp_path, content):
    cp, jp, _, rows = _files(tmp_path, 1)
    _restricted_job(rows[0])["description_text"] += "\n" + content
    rows[0]["normalized_text_sha256"] = hashlib.sha256(rows[0]["description_text"].encode()).hexdigest()
    _write_rows(jp, rows)
    with pytest.raises(ValueError, match="personal identifier"):
        load_corpus(cp, jp)


def test_labelled_job_update_date_is_not_a_phone_and_candidates_are_unchanged(tmp_path):
    cp, jp, candidates, rows = _files(tmp_path, 1)
    rows[0]["description_paraphrase"] += "\nUpdated 22.10.2026"
    _write_rows(jp, rows)
    load_corpus(cp, jp)
    rows[0]["description_paraphrase"] += "\nCall +45 12345678"
    _write_rows(jp, rows)
    with pytest.raises(ValueError, match="personal identifier"):
        load_corpus(cp, jp)
    candidates[0]["profile_summary"] += "\nUpdated 22.10.2026"
    _write_rows(cp, candidates)
    with pytest.raises(ValueError, match="candidate .*personal identifier"):
        load_corpus(cp, jp)


def test_modern_job_placeholders_duplicates_and_mislabelled_verbatim_rejected(tmp_path):
    cp, jp, _, rows = _files(tmp_path, 2)
    for row in rows:
        _restricted_job(row)
    rows[0]["description_text"] = "TBD"
    _write_rows(jp, rows)
    with pytest.raises(ValueError, match="placeholder description_text"):
        load_corpus(cp, jp)
    rows[0]["description_text"] = rows[1]["description_text"]
    rows[0]["id"] = rows[1]["id"]
    _write_rows(jp, rows)
    with pytest.raises(ValueError, match="duplicate ID"):
        load_corpus(cp, jp)
    rows[0]["id"] = "job_00"
    rows[0]["description_paraphrase"] = rows[0]["description_text"]
    _write_rows(jp, rows)
    with pytest.raises(ValueError, match="must not be labelled"):
        load_corpus(cp, jp)


def test_private_local_job_corpus_and_frozen_candidates_read_only():
    location = os.environ.get("PHASE5_LOCAL_CORPUS_DIR")
    if not location:
        pytest.skip("Private local evaluation corpus not configured")
    directory = Path(location)
    candidate_path, job_path = directory / "candidates.jsonl", directory / "jobs.jsonl"
    before = candidate_path.read_bytes()
    candidates, jobs = load_corpus(candidate_path, job_path)
    assert len(candidates) == 8 and len(jobs) == 30
    assert all(j["content_mode"] == "verbatim_restricted" and j["redistribution_allowed"] is False for j in jobs.values())
    for job in jobs.values():
        text_path = directory / "source-jobs-normalized" / f"{job['job_id']}.txt"
        assert text_path.read_text() == job["description_text"]
        assert hashlib.sha256((directory / "source-jobs" / job["pdf_filename"]).read_bytes()).hexdigest() == job["pdf_sha256"]
    assert candidate_path.read_bytes() == before
