from fastapi.testclient import TestClient

from app.nlp.skill_extractor import SkillExtractor
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


def test_job_processing_extracts_requirement_skills(client: TestClient) -> None:
    headers = auth_headers(client)
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


def test_matching_recommends_jobs_with_skill_gaps(client: TestClient) -> None:
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
        headers=headers,
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
