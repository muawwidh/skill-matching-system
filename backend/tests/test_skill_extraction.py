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


def test_matching_recommends_jobs_with_skill_gaps(client: TestClient, db_session: Session) -> None:
    headers = auth_headers(client)
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

    job_response = client.post(
        "/jobs",
        headers=job_manager_headers(client, db_session),
        json={
            "title": "API Engineer",
            "company": "Acme",
            "location": "Remote",
            "employment_type": "Full-time",
            "description": "Required skills\nPython\nDocker\n\nPreferred skills\nFastAPI",
        },
    )
    assert job_response.status_code == 201

    recommendations_response = client.post("/matches/recommendations/refresh", headers=headers)
    assert recommendations_response.status_code == 200
    recommendations = recommendations_response.json()
    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation["score"] == 60.0
    assert recommendation["matched_required"] == ["python"]
    assert recommendation["matched_preferred"] == ["fastapi"]
    assert recommendation["missing_required"] == ["docker"]
    assert recommendation["job"]["title"] == "API Engineer"
