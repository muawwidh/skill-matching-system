import math
from uuid import UUID, uuid4

import pytest

from app.retrieval.matching_comparison import coverage_order, ndcg_at_k, score_rankings
from app.services.matching_service import SkillItem


def _item(name, concept=None, requirement="", skill_type="skill"):
    return SkillItem(name=name, skill_type=skill_type, concept_id=concept,
                     concept_label=f"{name} (concept)" if concept else None, requirement=requirement)


def test_ndcg_uses_graded_gain_and_log_discount() -> None:
    grades = {"a": 2, "b": 1, "c": 0}
    assert ndcg_at_k(["a", "b", "c"], grades) == pytest.approx(1.0)
    # Swapping the grade-2 and grade-1 jobs: DCG = 1/1 + 3/log2(3); ideal = 3/1 + 1/log2(3).
    expected = (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3))
    assert ndcg_at_k(["b", "a", "c"], grades) == pytest.approx(expected)
    # Only the top k count.
    assert ndcg_at_k(["c", "b", "a"], grades, k=1) == 0.0
    assert ndcg_at_k(["a"], {"a": 0, "b": 0}) is None


def test_name_only_variant_ignores_taxonomy_links() -> None:
    python = uuid4()
    candidate = [_item("python3", python)]                     # same concept, different name
    jobs = {"job_concept": [_item("python", python, "required")],
            "job_name": [_item("python3", None, "required"), _item("docker", None, "required")]}
    ids = {"job_concept": UUID(int=1), "job_name": UUID(int=2)}
    # C: the concept match gives 1/1 required, ahead of 1/2.
    assert coverage_order(candidate, jobs, ids) == ["job_concept", "job_name"]
    # B: links ignored, so only the same-name job matches (1/2 beats 0/1).
    assert coverage_order(candidate, jobs, ids, use_concepts=False) == ["job_name", "job_concept"]


def test_ties_fall_to_job_id_without_similarity_and_to_similarity_with_it() -> None:
    candidate = [_item("sql")]
    jobs = {"first": [_item("sql", None, "required")], "second": [_item("sql", None, "required")]}
    ids = {"first": UUID(int=2), "second": UUID(int=1)}
    assert coverage_order(candidate, jobs, ids) == ["second", "first"]               # by job ID
    assert coverage_order(candidate, jobs, ids, similarity={"first": 0.9, "second": 0.1}) == ["first", "second"]


def test_scores_use_evaluation_definitions_with_exact_fractions() -> None:
    judgments = {("c1", "j1"): {"relevance_grade": "2"}, ("c1", "j2"): {"relevance_grade": "1"},
                 ("c1", "j3"): {"relevance_grade": "2"}, ("c1", "j4"): {"relevance_grade": "0"}}
    rankings = {"A": {"c1": ["j2", "j1", "j4", "j3"]}}
    result = score_rankings(rankings, judgments, ["c1"])["A"]
    query = result["per_query"]["c1"]
    assert query["first_grade2_rank"] == 2 and query["mrr"] == 0.5
    assert query["recall_at_5"] == 1.0
    assert result["macro_exact_fraction"]["mrr"] == "1/2"
    assert 0 < query["ndcg_at_10"] < 1
