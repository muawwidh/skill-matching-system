"""Synthetic eligibility fixtures only; no real ranking or retrieval quality measurement."""

import csv
import hashlib
import json

import pytest

from app.retrieval import benchmark
from app.retrieval.evaluation_policy import EvaluationPolicy
from app.retrieval.representation import MODEL_ID, MODEL_REVISION, TEMPLATE_VERSION
from test_retrieval_benchmark import _files


POST_JUDGMENT_SENTENCE = "This coverage exception was adopted after the relevance judgments were collected."


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def pack(tmp_path):
    cp, jp, candidates, jobs = _files(tmp_path, 30)
    candidates = [{**candidates[0], "id": f"candidate_{i}"} for i in range(8)]
    binding = {"corpus_freeze_id": "freeze_synthetic", "corpus_sha256": "a" * 64}
    candidates = [{**row, **binding} for row in candidates]
    jobs = [{**row, **binding} for row in jobs]
    _write_jsonl(cp, candidates)
    _write_jsonl(jp, jobs)
    rows = [dict(candidate_id=c["id"], job_id=j["id"],
                 relevance_grade="2" if i < 7 and k == 0 else "1" if k == 1 else "0",
                 reviewer_id="synthetic_reviewer", judgment_date="2026-11-04",
                 rationale="Synthetic eligibility fixture only", uncertainty_flag="false", **binding)
            for i, c in enumerate(candidates) for k, j in enumerate(jobs)]
    judgments = tmp_path / "judgments.csv"
    _write_csv(judgments, rows)
    policy = {"schema_version": "phase5-evaluation-policy-v1", "methodology_version": "coverage-v1",
              "decision_date": "2026-11-04", **binding, "post_judgment_protocol_deviation": True,
              "input_sha256": {"candidates": _sha(cp), "jobs": _sha(jp), "judgments": _sha(judgments)},
              "exceptions": [{"candidate_id": "candidate_7", "reason": "No clearly relevant job in frozen synthetic corpus",
                              "grade2_coverage_status": "no_grade2_jobs",
                              "metric_treatment": {"recall_at_k": "undefined", "mrr": "undefined"},
                              "exclude_from_aggregate_binary_query_denominator": True,
                              "retain_for_graded_descriptive_analyses": True}]}
    pp = tmp_path / "policy.json"
    pp.write_text(json.dumps(policy))
    return cp, jp, judgments, pp, policy, rows


def _validate(pack):
    cp, jp, judgments, pp, policy, _ = pack
    pp.write_text(json.dumps(policy))
    return benchmark.validate_benchmark(cp, jp, judgments, pp)


def test_strict_default_and_explicit_coverage_without_changing_240_judgments(pack):
    cp, jp, judgments, _, _, _ = pack
    before = judgments.read_bytes()
    with pytest.raises(ValueError, match="no grade-2"):
        benchmark.validate_benchmark(cp, jp, judgments)
    result = _validate(pack)
    assert result["judged_pairs"] == 240
    coverage = result["query_coverage"]
    assert (coverage["total_queries"], coverage["evaluable_grade2_queries"],
            coverage["excluded_undefined_queries"], coverage["grade2_query_coverage"],
            coverage["aggregate_binary_query_denominator"]) == (8, 7, 1, "7/8", 7)
    assert coverage["excluded_queries"][0]["candidate_id"] == "candidate_7"
    assert coverage["excluded_queries"][0]["reason"]
    assert POST_JUDGMENT_SENTENCE in coverage["limitation"]
    assert "undefined is not zero" in coverage["limitation"]
    assert coverage["policy"]["post_judgment_protocol_deviation"] is True
    assert "source_decision_sha256" not in json.dumps(result)
    assert "source_decision_sha256" not in EvaluationPolicy.model_validate(pack[4]).model_dump()
    assert result["reviewer_limitations"]["single_rater"] is True
    assert result["reviewer_limitations"]["inter_rater_reliability_estimate"] is None
    assert judgments.read_bytes() == before


@pytest.mark.parametrize("field,value", [("corpus_freeze_id", "wrong_freeze"), ("corpus_sha256", "b" * 64)])
def test_policy_rejects_wrong_freeze_or_hash(pack, field, value):
    pack[4][field] = value
    with pytest.raises(ValueError, match="freeze identity/hash mismatch"):
        _validate(pack)


@pytest.mark.parametrize("name", ["candidates", "jobs", "judgments"])
def test_policy_binds_each_exact_input_file(pack, name):
    pack[4]["input_sha256"][name] = "b" * 64
    with pytest.raises(ValueError, match="checksum mismatch"):
        _validate(pack)


@pytest.mark.parametrize("candidate,message", [("unknown_candidate", "unknown candidate"),
                                               ("candidate_0", "cannot exclude")])
def test_unknown_or_positive_candidate_cannot_be_excluded(pack, candidate, message):
    pack[4]["exceptions"][0]["candidate_id"] = candidate
    with pytest.raises(ValueError, match=message):
        _validate(pack)


@pytest.mark.parametrize("field,value", [("reason", None), ("reason", " "), ("reason", "TBD"),
    ("metric_treatment", None), ("metric_treatment", {"recall_at_k": "zero", "mrr": "undefined"}),
    ("exclude_from_aggregate_binary_query_denominator", False),
    ("retain_for_graded_descriptive_analyses", False),
    ("retain_for_graded_descriptive_analyses", "true"), ("grade2_coverage_status", "covered")])
def test_reason_and_explicit_undefined_retention_treatment_are_required(pack, field, value):
    exception = pack[4]["exceptions"][0]
    if value is None:
        exception.pop(field)
    else:
        exception[field] = value
    with pytest.raises(ValueError):
        _validate(pack)


@pytest.mark.parametrize("field,value", [("decision_date", "20261104"), ("decision_date", "2026-02-30"),
    ("methodology_version", ""), ("post_judgment_protocol_deviation", "true"),
    ("schema_version", "unrecognized")])
def test_policy_metadata_is_required_and_validated(pack, field, value):
    pack[4][field] = value
    with pytest.raises(ValueError):
        _validate(pack)


@pytest.mark.parametrize("value", [False, None, "true", "false", 0, 1, [], {}])
def test_post_judgment_declaration_rejects_false_null_and_non_booleans(pack, value):
    pack[4]["post_judgment_protocol_deviation"] = value
    with pytest.raises(ValueError, match="post_judgment_protocol_deviation"):
        _validate(pack)


def test_post_judgment_declaration_cannot_be_omitted(pack):
    pack[4].pop("post_judgment_protocol_deviation")
    with pytest.raises(ValueError, match="post_judgment_protocol_deviation"):
        _validate(pack)


def test_removed_source_decision_hash_is_an_extra_forbidden_field(pack):
    pack[4]["source_decision_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="Extra inputs are not permitted") as exc:
        _validate(pack)
    assert "source_decision_sha256" in str(exc.value)


def test_second_undeclared_zero_positive_candidate_is_not_silently_excluded(pack):
    _, _, judgments, _, policy, rows = pack
    for row in rows:
        if row["candidate_id"] == "candidate_6":
            row["relevance_grade"] = "0"
    _write_csv(judgments, rows)
    policy["input_sha256"]["judgments"] = _sha(judgments)
    with pytest.raises(ValueError, match="candidate_6 has no grade-2"):
        _validate(pack)


def test_duplicate_exception_and_duplicate_json_keys_are_rejected(pack):
    pack[4]["exceptions"] *= 2
    with pytest.raises(ValueError, match="duplicate candidate exceptions"):
        _validate(pack)
    cp, jp, judgments, pp, _, _ = pack
    pp.write_text('{"schema_version":"x","schema_version":"y"}')
    with pytest.raises(ValueError, match="Duplicate evaluation-policy key"):
        benchmark.validate_benchmark(cp, jp, judgments, pp)


@pytest.mark.parametrize("kind", ["candidates", "jobs", "judgments"])
def test_every_record_requires_matching_freeze_binding(pack, kind):
    cp, jp, judgments, _, policy, rows = pack
    path = {"candidates": cp, "jobs": jp, "judgments": judgments}[kind]
    if kind == "judgments":
        rows[0]["corpus_freeze_id"] = "other"
        _write_csv(path, rows)
    else:
        records = [json.loads(line) for line in path.read_text().splitlines()]
        records[0].pop("corpus_sha256")
        _write_jsonl(path, records)
    policy["input_sha256"][kind] = _sha(path)
    with pytest.raises(ValueError, match="freeze identity/hash mismatch"):
        _validate(pack)


@pytest.mark.parametrize("fault,message", [("missing", "Missing 1"), ("duplicate", "duplicate pair"),
                                           ("blank", "invalid or missing grade")])
def test_policy_does_not_bypass_complete_unique_graded_matrix(pack, fault, message):
    _, _, judgments, _, policy, rows = pack
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows.append(rows[0].copy())
    else:
        rows[0]["relevance_grade"] = ""
    _write_csv(judgments, rows)
    policy["input_sha256"]["judgments"] = _sha(judgments)
    with pytest.raises(ValueError, match=message):
        _validate(pack)


def test_policy_requires_complete_validation_and_bound_corpus_paths(pack):
    cp, jp, judgments, pp, _, _ = pack
    candidates, jobs = benchmark.load_corpus(cp, jp)
    with pytest.raises(ValueError, match="requires complete"):
        benchmark.load_judgments(judgments, candidates, jobs, False, policy_path=pp)
    with pytest.raises(ValueError, match="requires candidate and job corpus paths"):
        benchmark.load_judgments(judgments, candidates, jobs, policy_path=pp)
    with pytest.raises(ValueError, match="requires a judgment export"):
        benchmark.validate_benchmark(cp, jp, policy_path=pp)


def test_policy_rejects_changed_judgment_export_even_with_identical_parsed_values(pack):
    pack[2].write_bytes(pack[2].read_bytes().replace(b"\r\n", b"\n"))
    with pytest.raises(ValueError, match="judgments checksum mismatch"):
        _validate(pack)


def test_duplicate_candidate_and_all_excluded_queries_fail(pack):
    cp, _, judgments, _, policy, rows = pack
    original = cp.read_bytes()
    cp.write_bytes(original + original.splitlines(keepends=True)[0])
    with pytest.raises(ValueError, match="duplicate ID"):
        _validate(pack)
    cp.write_bytes(original)
    for row in rows:
        row["relevance_grade"] = "0"
    _write_csv(judgments, rows)
    policy["input_sha256"]["judgments"] = _sha(judgments)
    prototype = policy["exceptions"][0]
    policy["exceptions"] = [{**prototype, "candidate_id": f"candidate_{i}"} for i in range(8)]
    with pytest.raises(ValueError, match="no evaluable grade-2 queries"):
        _validate(pack)


def test_mocked_evaluator_excludes_only_binary_denominator_and_retains_grade_one(pack, monkeypatch, tmp_path):
    """Mocked aggregation test: no vectors, retrieval engine or real quality calculation."""
    cp, jp, judgments, pp, _, _ = pack
    original = benchmark._jsonl
    sentinel = tmp_path / "mock-input"
    sentinel.write_text("mock provenance only")
    candidates, jobs = benchmark.load_corpus(cp, jp)
    provenance = {"model_id": MODEL_ID, "model_revision": MODEL_REVISION, "template_version": TEMPLATE_VERSION,
                  "corpus_sha256": {"candidates": _sha(cp), "jobs": _sha(jp)}}
    mock_rows = [{"candidate_id": c, "retrieved_job_ids": list(jobs), **provenance} for c in candidates]
    monkeypatch.setattr(benchmark, "_jsonl", lambda path: mock_rows if path == sentinel else original(path))
    calls = []

    def mock_metrics(items):
        calls.append(items)
        return {"recall_at_5": 0.5, "recall_at_10": 0.5, "recall_at_20": 0.5, "mrr": 0.5}

    monkeypatch.setattr(benchmark, "retrieval_metrics", mock_metrics)
    before = judgments.read_bytes()
    result = benchmark.evaluate_pack(cp, jp, judgments, sentinel, policy_path=pp)
    assert len(calls) == 7
    assert set(result["macro_average"].values()) == {0.5}
    excluded = result["per_candidate"]["candidate_7"]
    assert excluded["status"] == "undefined"
    assert all(excluded[key] is None for key in result["macro_average"])
    assert result["query_coverage"]["aggregate_binary_query_denominator"] == 7
    assert POST_JUDGMENT_SENTENCE in result["query_coverage"]["limitation"]
    assert "source_decision_sha256" not in json.dumps(result)
    assert result["data_sha256"]["evaluation_policy"] == _sha(pp)
    calls.clear()
    exploratory = benchmark.evaluate_pack(cp, jp, judgments, sentinel, grade_one=True, policy_path=pp)
    assert len(calls) == 15
    assert exploratory["exploratory_query_coverage"]["aggregate_query_denominator"] == 8
    assert exploratory["exploratory_per_candidate"]["candidate_7"]["relevant_count"] == 1
    mock_rows.pop()
    with pytest.raises(ValueError, match="Rankings missing candidate profiles"):
        benchmark.evaluate_pack(cp, jp, judgments, sentinel, policy_path=pp)
    assert judgments.read_bytes() == before


def test_validate_cli_accepts_explicit_policy_without_metrics(pack, monkeypatch, capsys):
    from app.retrieval.cli import main

    cp, jp, judgments, pp, _, _ = pack
    monkeypatch.setattr("sys.argv", ["retrieval", "validate-benchmark", str(cp), str(jp),
                                    "--judgments", str(judgments), "--evaluation-policy", str(pp)])
    monkeypatch.setattr(benchmark, "retrieval_metrics", lambda _: pytest.fail("Validation must not calculate metrics"))
    main()
    assert json.loads(capsys.readouterr().out)["query_coverage"]["grade2_query_coverage"] == "7/8"
