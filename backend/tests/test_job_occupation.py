"""Job occupation (D060): title linked with clean-up and the automatic-approval rule, else not determined."""
from app.db.models import Job
from app.services.experience_service import ExperienceService
from tests.esco_occupations import add_esco_occupations
from tests.test_recommendations import candidate_with_skills, create_job, manager


def test_job_titles_link_automatically_or_stay_not_determined(db_session):
    add_esco_occupations(db_session)
    service = ExperienceService(db_session)
    jobs = {title: Job(title=title, description="x", cleaned_description="x", status="processed", source=source)
            for title, source in (("Senior Software Engineer (m/w/d)", "arbeitnow"), ("Sales Manager - DACH", "manual"),
                                  ("Office Wizard", "greenhouse"), ("Software Engineer", "evaluation"))}
    result = {title: service.job_occupation(job) for title, job in jobs.items()}
    assert result["Senior Software Engineer (m/w/d)"]["label"] == "software developer"
    assert result["Senior Software Engineer (m/w/d)"]["isco_code"] == "2512"
    assert result["Sales Manager - DACH"]["isco_code"] == "1221"
    assert result["Office Wizard"] == {"determined": False, "concept_id": None, "label": None, "isco_code": None,
                                       "isco_unit_group": ""}
    assert result["Software Engineer"]["determined"] is False  # evaluation jobs are never linked


def test_recommendations_carry_the_job_occupation(client, db_session, fake_retrieval):
    add_esco_occupations(db_session)
    staff = manager(client, db_session)
    linked = create_job(client, staff, "Software Engineer", "Python")
    other = create_job(client, staff, "Office Wizard", "Python")
    headers = candidate_with_skills(client)
    items = {item["job_id"]: item for item in client.get("/matches/recommendations", headers=headers).json()["results"]}
    assert items[linked]["job_occupation"]["label"] == "software developer"
    assert items[other]["job_occupation"]["determined"] is False
