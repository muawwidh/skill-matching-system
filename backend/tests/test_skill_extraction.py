import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExtractedCandidateTerm, ExtractedJobTerm, Role, User
from app.nlp.skill_extractor import (
    EXTRACTION_CONTRACT_VERSION,
    SkillDictionary,
    SkillDictionaryEntry,
    SkillExtractor,
)
from app.services.section_detection_service import SectionDetectionService


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": "skills@example.com",
            "full_name": "Skill Reviewer",
            "password": "correct-horse-password",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def job_manager_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": "job-manager@example.com",
            "full_name": "Synthetic Job Manager",
            "password": "correct-horse-password",
        },
    )
    assert response.status_code == 201
    user = db_session.scalar(select(User).where(User.email == "job-manager@example.com"))
    assert user is not None
    user.roles.append(Role(name="admin", description="Job management"))
    db_session.commit()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_skill_extractor_finds_dictionary_and_regex_terms() -> None:
    text = "Skills\nPython, FastAPI, SQL\n\nExperience\n5 years experience building REST APIs"
    sections = SectionDetectionService().detect(text)
    terms = SkillExtractor().extract_from_sections(sections, text, "candidate")
    normalized_terms = {term.normalized_text for term in terms}
    term_types = {term.term_type for term in terms}
    assert {"python", "fastapi", "sql", "rest api"} <= normalized_terms
    assert "experience_indicator" in term_types
    assert all(term.evidence_sentence for term in terms)


def test_skill_extractor_trims_evidence_from_dense_skill_lists() -> None:
    text = (
        "Skills\n"
        "Python, FastAPI • REST API Development • OpenAI API integration • "
        "Prompt Engineering • Git & GitHub • API Testing (Postman)"
    )
    sections = SectionDetectionService().detect(text)
    terms = SkillExtractor().extract_from_sections(sections, text, "candidate")
    by_name = {term.normalized_text: term.evidence_sentence for term in terms}

    assert by_name["python"] == "Python"
    assert by_name["fastapi"] == "FastAPI"
    assert by_name["git"] == "Git & GitHub"
    assert len(by_name["python"]) < 30


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Experience with SQL.", {"sql"}),
        ("Used Docker, Git, and Python.", {"docker", "git", "python"}),
        ("Skills include FastAPI; PostgreSQL: advanced.", {"fastapi", "postgresql"}),
        ("Built systems with React!", {"react"}),
        ("Worked with Java?", {"java"}),
        ("Used PYTHON", {"python"}),
        ("Used Python)", {"python"}),
    ],
)
def test_dictionary_punctuation_and_case_preserve_offsets_and_evidence(text: str, expected: set[str]) -> None:
    extractor = SkillExtractor()
    extractor.spacy_nlp = None
    extractor.spacy_matcher = None
    terms = extractor.extract_from_sections(SectionDetectionService().detect(text), text, "candidate")
    dictionary_terms = [term for term in terms if term.extraction_method.startswith("dictionary@")]
    assert {term.normalized_text for term in dictionary_terms} == expected
    for term in dictionary_terms:
        assert text[term.start_char : term.end_char] == term.raw_text
        assert term.raw_text.lower() in term.evidence_sentence.lower()
        assert term.extraction_method == f"dictionary@{EXTRACTION_CONTRACT_VERSION}"


def test_dictionary_boundaries_protect_technical_names_and_substrings() -> None:
    dictionary = SkillDictionary(
        [
            SkillDictionaryEntry(label=name, term_type="skill", aliases=(name.lower(),))
            for name in ("C++", "C#", ".NET", "Node.js", "Java", "TypeScript", "React")
        ]
    )
    extractor = SkillExtractor(dictionary)
    extractor.spacy_nlp = None
    extractor.spacy_matcher = None
    text = "C++ C# .NET Node.js Java TypeScript; reactive javascript typescriptish C++Plus Node.jsx"
    terms = extractor.extract_from_sections(SectionDetectionService().detect(text), text, "candidate")
    assert {term.normalized_text for term in terms} == {
        "c++", "c#", ".net", "node.js", "java", "typescript"
    }
    assert all(text[term.start_char : term.end_char] == term.raw_text for term in terms)


def test_dictionary_dotted_identifier_boundary_requires_complete_skill_token() -> None:
    dictionary = SkillDictionary(
        [
            SkillDictionaryEntry(label="Python", term_type="skill", aliases=("python",)),
            SkillDictionaryEntry(label="Node.js", term_type="tool", aliases=("node.js",)),
        ]
    )
    extractor = SkillExtractor(dictionary)
    extractor.spacy_nlp = None
    extractor.spacy_matcher = None
    text = "Python.org Python. Node.js Node.js.example"
    terms = extractor.extract_from_sections(SectionDetectionService().detect(text), text, "candidate")
    assert [(term.normalized_text, term.raw_text, term.start_char, term.end_char) for term in terms] == [
        ("python", "Python", text.index("Python. "), text.index("Python. ") + len("Python")),
        ("node.js", "Node.js", text.index("Node.js "), text.index("Node.js ") + len("Node.js")),
    ]
    assert all(term.extraction_method == "dictionary@v2" for term in terms)


def test_optional_spacy_method_keeps_distinct_versioned_provenance() -> None:
    class FakeSpan:
        text = "Python"
        start_char = 0
        end_char = 6

    class FakeDocument:
        def __getitem__(self, item):
            return FakeSpan()

    class FakeNlp:
        vocab = type("Vocab", (), {"strings": {1: "Python::skill"}})()

        def __call__(self, text):
            return FakeDocument()

    extractor = SkillExtractor()
    extractor.spacy_nlp = FakeNlp()
    extractor.spacy_matcher = lambda document: [(1, 0, 1)]
    terms = extractor.extract_from_sections(SectionDetectionService().detect("Python"), "Python", "candidate")
    assert len(terms) == 1
    assert terms[0].extraction_method == "spacy_phrase_matcher@v2"
    assert (terms[0].raw_text, terms[0].start_char, terms[0].end_char) == ("Python", 0, 6)


def test_versioned_extraction_methods_are_persisted_for_candidate_and_job(
    client: TestClient, db_session: Session
) -> None:
    assert EXTRACTION_CONTRACT_VERSION == "v2"
    headers = auth_headers(client)
    cv = client.post(
        "/cvs/paste",
        headers=headers,
        json={"text": "Skills: Python. 5 years experience", "original_filename": "version.txt", "consent_to_process": True},
    )
    assert cv.status_code == 201
    job = client.post(
        "/jobs",
        headers=job_manager_headers(client, db_session),
        json={
            "title": "Engineer", "company": "Example", "location": "Remote",
            "employment_type": "Full-time", "description": "Required skills: SQL. 3 years experience",
        },
    )
    assert job.status_code == 201
    candidate_methods = set(db_session.scalars(select(ExtractedCandidateTerm.extraction_method)))
    job_methods = set(db_session.scalars(select(ExtractedJobTerm.extraction_method)))
    assert {"dictionary@v2", "regex@v2"} <= candidate_methods
    assert {"dictionary@v2", "regex@v2"} <= job_methods


def test_cv_processing_extracts_and_reviews_candidate_skills(client: TestClient) -> None:
    headers = auth_headers(client)
    cv_response = client.post(
        "/cvs/paste",
        headers=headers,
        json={
            "text": "Summary\nBackend engineer\n\nSkills\nPython\nFastAPI\nSQL",
            "original_filename": "skills-cv.txt",
            "consent_to_process": True,
        },
    )
    assert cv_response.status_code == 201
    cv_id = cv_response.json()["id"]

    skills_response = client.get(f"/cvs/{cv_id}/extracted-skills", headers=headers)
    assert skills_response.status_code == 200
    skills = skills_response.json()
    assert {skill["normalized_text"] for skill in skills} >= {"python", "fastapi", "sql"}

    first_skill = skills[0]
    first_skill["review_status"] = "approved"
    first_skill["raw_text"] = "Python 3"
    first_skill["normalized_text"] = "python 3"
    review_response = client.put(
        f"/cvs/{cv_id}/extracted-skills",
        headers=headers,
        json={"skills": skills},
    )
    assert review_response.status_code == 200
    assert any(skill["normalized_text"] == "python 3" for skill in review_response.json())


def test_job_processing_extracts_requirement_skills(client: TestClient, db_session: Session) -> None:
    headers = job_manager_headers(client, db_session)
    job_response = client.post(
        "/jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Remote",
            "employment_type": "Full-time",
            "description": "Required skills\nPython\nDocker\n\nPreferred skills\nKubernetes\nCI/CD",
        },
    )
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    skills_response = client.get(f"/jobs/{job_id}/extracted-skills", headers=headers)
    assert skills_response.status_code == 200
    skills = skills_response.json()
    by_name = {skill["normalized_text"]: skill["requirement_type"] for skill in skills}
    assert by_name["python"] == "required"
    assert by_name["docker"] == "required"
    assert by_name["kubernetes"] == "preferred"
    assert all("occurrences" not in skill and "taxonomy" not in skill for skill in skills)
    target = skills[0]
    target["review_status"] = "rejected"
    updated = client.put(f"/jobs/{job_id}/extracted-skills/{target['id']}", headers=headers, json=target)
    assert updated.status_code == 200
    assert updated.json()["id"] == target["id"]
    assert updated.json()["review_status"] == "rejected"
    assert updated.json()["requirement_type"] == target["requirement_type"]


def test_matching_reports_coverage_counts_from_approved_skills(client: TestClient, db_session: Session) -> None:
    headers = auth_headers(client)
    manager = job_manager_headers(client, db_session)
    cv_response = client.post(
        "/cvs/paste",
        headers=headers,
        json={
            "text": "Summary\nBackend engineer\n\nSkills\nPython\nFastAPI",
            "original_filename": "matching-cv.txt",
            "consent_to_process": True,
        },
    )
    assert cv_response.status_code == 201
    cv_id = cv_response.json()["id"]

    job_response = client.post(
        "/jobs",
        headers=manager,
        json={
            "title": "API Engineer",
            "company": "Acme",
            "location": "Remote",
            "employment_type": "Full-time",
            "description": "Required skills\nPython\nDocker\nBachelor's degree\n\nPreferred skills\nFastAPI",
        },
    )
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    # Pending skills on either side are never compared.
    pending = client.get("/matches/recommendations", headers=headers).json()[0]
    assert pending["matched_required"] == [] and pending["matched_preferred"] == []
    assert pending["missing_required"] == [] and pending["missing_preferred"] == []

    cv_skills = client.get(f"/cvs/{cv_id}/extracted-skills", headers=headers).json()
    for skill in cv_skills:
        skill["review_status"] = "approved"
    assert client.put(f"/cvs/{cv_id}/extracted-skills", headers=headers, json={"skills": cv_skills}).status_code == 200
    for skill in client.get(f"/jobs/{job_id}/extracted-skills", headers=manager).json():
        skill["review_status"] = "approved"
        assert client.put(f"/jobs/{job_id}/extracted-skills/{skill['id']}", headers=manager, json=skill).status_code == 200

    # GET recomputes, so approvals are reflected without an explicit refresh.
    recommendations = client.get("/matches/recommendations", headers=headers).json()
    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation["matched_required"] == [{"label": "python", "matched_via": "skill_name"}]
    assert recommendation["matched_preferred"] == [{"label": "fastapi", "matched_via": "skill_name"}]
    # Docker has no approved taxonomy link and no same-name CV skill: not compared, not "missing".
    assert recommendation["missing_required"] == []
    assert recommendation["missing_preferred"] == []
    assert recommendation["score"] == 100.0
    assert recommendation["job_skill_count"] == 2
    explanation = recommendation["explanation"].splitlines()
    assert explanation[0] == "Required skills: 1 of 1 matched (python)."
    assert explanation[1] == "Preferred skills: 1 of 1 matched (fastapi)."
    assert "1 job skill could not be compared" in explanation[2] and explanation[2].endswith(": docker.")
    assert explanation[3] == "Also required — not assessed by the system: bachelor's degree."
    assert "%" not in recommendation["explanation"]
    assert recommendation["job"]["title"] == "API Engineer"

    refreshed = client.post("/matches/recommendations/refresh", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()[0]["matched_required"] == recommendation["matched_required"]


def _item(name, concept=None, requirement="", skill_type="skill"):
    from app.services.matching_service import SkillItem

    return SkillItem(name=name, skill_type=skill_type, concept_id=concept,
                     concept_label=f"{name} (concept)" if concept else None, requirement=requirement)


def test_coverage_prefers_concepts_and_falls_back_to_names_only_when_not_both_linked() -> None:
    from uuid import uuid4

    from app.services.matching_service import compute_coverage

    python, java, docker, git = uuid4(), uuid4(), uuid4(), uuid4()
    candidate = [
        _item("python3", python),          # different name, same concept
        _item("java", uuid4()),            # same name, different concept
        _item("docker"),                   # unlinked, same name as a linked job skill
        _item("excel"),                    # unlinked, same name as an unlinked job skill
    ]
    job = [
        _item("python", python, "required"),
        _item("java", java, "required"),
        _item("docker", docker, "required"),
        _item("git", git, "required"),
        _item("excel", None, "unknown"),
        _item("rust", None, "required"),
    ]
    result = compute_coverage(candidate, job)
    assert result.matched_required == [
        {"label": "docker (concept)", "matched_via": "skill_name"},
        {"label": "python (concept)", "matched_via": "taxonomy_concept"},
    ]
    # Both linked to different concepts: no name fallback, so Java is missing.
    assert result.missing_required == ["git (concept)", "java (concept)"]
    # `unknown` counts as preferred.
    assert result.matched_preferred == [{"label": "excel", "matched_via": "skill_name"}]
    assert result.not_compared == ["rust"]
    assert (result.required_total, result.preferred_total) == (4, 1)


def test_coverage_deduplicates_and_lists_non_skill_terms_without_scoring() -> None:
    from uuid import uuid4

    from app.services.matching_service import compute_coverage

    sql = uuid4()
    job = [
        _item("sql", sql, "preferred"),
        _item("sql", sql, "required"),            # same concept listed twice: required wins
        _item("sql", None, "unknown"),            # unlinked duplicate joins the concept group
        _item("bachelor's degree", None, "required", "qualification"),
        _item("3 years experience", None, "unknown", "experience_indicator"),
        _item("aws certified", None, "preferred", "certification"),
    ]
    result = compute_coverage([_item("bachelor's degree", None, "", "qualification")], job)
    assert result.missing_required == ["sql (concept)"]
    assert result.matched_preferred == [] and result.missing_preferred == []
    assert result.not_assessed_required == ["bachelor's degree"]
    assert result.not_assessed_preferred == ["3 years experience", "aws certified"]
    assert result.candidate_skill_count == 0


def test_ranking_is_lexicographic_without_weights() -> None:
    from types import SimpleNamespace
    from uuid import UUID

    from app.services.matching_service import ranking_key

    def match(job, matched_req, total_req, matched_pref=0, total_pref=0):
        return SimpleNamespace(
            job_id=UUID(int=job),
            matched_required=[{}] * matched_req, missing_required=["x"] * (total_req - matched_req),
            matched_preferred=[{}] * matched_pref, missing_preferred=["x"] * (total_pref - matched_pref),
        )

    jobs = {
        "no_required": (match(1, 0, 0, 3, 3), 0.99),
        "half_required": (match(2, 1, 2, 0, 1), 0.99),
        "full_no_preferred": (match(3, 2, 2), 0.99),
        "full_some_preferred": (match(4, 1, 1, 0, 4), None),
        "third_low_sim": (match(5, 1, 3, 1, 1), 0.10),
        "third_high_sim": (match(6, 2, 6, 1, 1), 0.90),   # 2/6 == 1/3 exactly
        "third_unindexed": (match(7, 1, 3, 1, 1), None),
    }
    order = sorted(jobs, key=lambda name: ranking_key(*jobs[name]))
    assert order == ["full_some_preferred", "full_no_preferred", "half_required",
                     "third_high_sim", "third_low_sim", "third_unindexed", "no_required"]


def test_explanation_is_built_from_lists_without_cutoffs() -> None:
    from app.services.matching_service import CoverageResult, build_explanation

    empty = build_explanation(CoverageResult())
    assert empty.splitlines() == ["This job lists no comparable required skills.",
                                  "This job lists no comparable preferred skills."]
    text = build_explanation(CoverageResult(
        matched_required=[{"label": "python", "matched_via": "skill_name"}],
        missing_required=["docker", "sql"], missing_preferred=["kubernetes"],
        not_compared=["rust", "go"]))
    lines = text.splitlines()
    assert lines[0] == "Required skills: 1 of 3 matched (python); missing: docker, sql."
    assert lines[1] == "Preferred skills: 0 of 1 matched; missing: kubernetes."
    assert lines[2].startswith("2 job skills could not be compared")
    for banned in ("%", "Strong", "Partial", "Limited", "Low match"):
        assert banned not in text
