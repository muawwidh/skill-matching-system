from fastapi.testclient import TestClient

from app.services.document_parser_service import DocumentParserService
from app.services.pdf_text_normalization_service import PdfTextNormalizationService
from app.services.section_detection_service import SectionDetectionService
from app.services.text_cleaning_service import TextCleaningService


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": "candidate@example.com",
            "full_name": "Candidate Example",
            "password": "correct-horse-password",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_text_cleaning_collapses_extra_spacing() -> None:
    cleaned = TextCleaningService().clean(" Python\t\tFastAPI\n\n\n\nSQL ")
    assert cleaned == "Python FastAPI\n\nSQL"


def test_section_detection_finds_cv_sections() -> None:
    text = "Summary\nBackend engineer\n\nSkills\nPython\nSQL\n\nEducation\nMSc"
    sections = SectionDetectionService().detect(text)
    assert [section.section_type for section in sections] == ["summary", "skills", "education"]
    assert sections[1].content == "Python\nSQL"


def test_section_detection_handles_pdf_style_heading_variants() -> None:
    text = (
        "PROFESSIONAL SUMMARY:\nBackend engineer\n\n"
        "PROFESSIONAL EXPERIENCE\nBuilt APIs\n\n"
        "KEY SKILLS:\nPython\nSQL\n\n"
        "ACADEMIC QUALIFICATIONS\nMSc Computer Science"
    )
    sections = SectionDetectionService().detect(text)
    assert [section.section_type for section in sections] == [
        "summary",
        "work_experience",
        "skills",
        "education",
    ]


def test_pdf_text_normalizer_splits_inline_cv_headings() -> None:
    text = (
        "Jane Doe Professional Summary Backend engineer "
        "Work Experience Built APIs Education MSc Computer Science "
        "Skills Python SQL"
    )
    normalized = PdfTextNormalizationService().normalize(text)
    sections = SectionDetectionService().detect(normalized)
    assert {section.section_type for section in sections} >= {
        "summary",
        "work_experience",
        "education",
        "skills",
    }


def test_txt_parser_validates_supported_content() -> None:
    parser = DocumentParserService()
    parsed = parser.parse_upload("cv.txt", "text/plain", b"Skills\nPython")
    assert parsed.text == "Skills\nPython"


def test_candidate_can_paste_cv_and_view_sections(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/cvs/paste",
        headers=headers,
        json={
            "text": "Summary\nBackend engineer\n\nSkills\nPython\nFastAPI\n\nProjects\nAPI platform",
            "original_filename": "manual-cv.txt",
            "consent_to_process": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "processed"
    assert {section["section_type"] for section in body["sections"]} >= {"summary", "skills"}

    list_response = client.get("/cvs", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_cv_processing_requires_consent(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/cvs/paste",
        headers=headers,
        json={
            "text": "Skills\nPython",
            "original_filename": "manual-cv.txt",
            "consent_to_process": False,
        },
    )
    assert response.status_code == 400


def test_candidate_can_upload_txt_cv(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/cvs/upload",
        headers=headers,
        data={"consent_to_process": "true"},
        files={"file": ("cv.txt", b"Skills\nPython\nSQL", "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["content_type"] == "text/plain"


def test_job_creation_processes_sections(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Remote",
            "employment_type": "Full-time",
            "description": "Responsibilities\nBuild APIs\n\nRequired skills\nPython\nSQL",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "processed"
    assert {section["section_type"] for section in body["sections"]} >= {
        "responsibilities",
        "required_skills",
    }

    logs_response = client.get("/admin/logs", headers=headers)
    assert logs_response.status_code == 403
