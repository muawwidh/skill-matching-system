"""Unreviewed skills on live jobs count for coverage, flagged as not reviewed (D054)."""
from sqlalchemy import select

from app.db.models import Job, JobSkill, Role, User
from app.services.job_service import JobService
from app.services.matching_service import SkillItem, build_explanation, compute_coverage


def test_unreviewed_job_skills_are_flagged_in_entries_and_explanation():
    candidate = [SkillItem("python", "skill")]
    job = [SkillItem("python", "skill", requirement="required", reviewed=False),
           SkillItem("docker", "skill", requirement="required", reviewed=False),
           SkillItem("sql", "skill", requirement="preferred")]
    result = compute_coverage(candidate, job)
    assert result.matched_required == [{"label": "python", "matched_via": "skill_name", "reviewed": False}]
    assert result.missing_required == [{"label": "docker", "checked_via": "skill_name", "reviewed": False}]
    assert result.missing_preferred == [{"label": "sql", "checked_via": "skill_name"}]
    assert "Automatically extracted, not reviewed: python, docker." in build_explanation(result)
    # One approved occurrence makes the skill reviewed.
    both = compute_coverage(candidate, job + [SkillItem("python", "skill", requirement="required")])
    assert both.matched_required == [{"label": "python", "matched_via": "skill_name"}]


def _job(db, source, title):
    job = Job(title=title, description="Requirements\n- Python\n- Docker\n- Git",
              cleaned_description="Requirements\n- Python\n- Docker\n- Git", status="draft", source=source)
    db.add(job)
    db.flush()
    JobService(db)._process_existing_job(job)
    db.commit()
    return job


def _register(client, db, email, role=None):
    response = client.post("/auth/register", json={"email": email, "full_name": "Synthetic", "password": "correct-horse-password"})
    if role:
        user = db.scalar(select(User).where(User.email == email))
        user.roles.append(Role(name=role, description=""))
        db.commit()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_live_jobs_use_pending_skills_while_manual_and_evaluation_jobs_stay_approved_only(client, db_session, fake_retrieval):
    live = _job(db_session, "arbeitnow", "Live role")
    manual = _job(db_session, "manual", "Manual role")
    evaluation = _job(db_session, "evaluation", "Evaluation role")
    for job in (live, manual, evaluation):
        assert {s.review_status for s in db_session.scalars(select(JobSkill).where(JobSkill.job_id == job.id))} == {"pending"}
    git = db_session.scalar(select(JobSkill).where(JobSkill.job_id == live.id, JobSkill.normalized_text == "git"))
    git.review_status = "rejected"
    db_session.commit()

    headers = _register(client, db_session, "candidate@example.com")
    cv = client.post("/cvs/paste", headers=headers, json={
        "text": "Skills\nPython", "original_filename": "cv.txt", "consent_to_process": True}).json()
    skills = client.get(f"/cvs/{cv['id']}/extracted-skills", headers=headers).json()
    for skill in skills:
        skill["review_status"] = "approved"
    client.put(f"/cvs/{cv['id']}/extracted-skills", headers=headers, json={"skills": skills})

    live_coverage = client.get(f"/matches/jobs/{live.id}", headers=headers).json()
    assert [(e["label"], e["reviewed"]) for e in live_coverage["matched_preferred"] + live_coverage["matched_required"]] \
        == [("python", False)]
    missing = live_coverage["missing_required"] + live_coverage["missing_preferred"]
    assert [(e["label"], e["reviewed"]) for e in missing] == [("docker", False)]  # rejected git left out
    assert "Automatically extracted, not reviewed" in live_coverage["explanation"]
    body = client.get(f"/matches/jobs/{manual.id}", headers=headers).json()
    assert body["job_skill_count"] == 0 and body["matched_required"] == body["matched_preferred"] == []
    # Evaluation jobs are not in the candidate view (D056); their coverage stays approved-only.
    from app.services.matching_service import MatchingService
    service = MatchingService(db_session)
    profile = service.repository.get_or_create_candidate_profile(
        db_session.scalar(select(User).where(User.email == "candidate@example.com")).id)
    assert service._coverage(evaluation, service._candidate_items(profile.id))["job_skill_count"] == 0

    # Administrators can still review a live job; the approved skill is then reviewed.
    admin = _register(client, db_session, "admin@example.com", "admin")
    python = next(s for s in client.get(f"/jobs/{live.id}/extracted-skills", headers=admin).json()
                  if s["normalized_text"] == "python")
    python["review_status"] = "approved"
    assert client.put(f"/jobs/{live.id}/extracted-skills/{python['id']}", headers=admin, json=python).status_code == 200
    after = client.get(f"/matches/jobs/{live.id}", headers=headers).json()
    assert [e.get("reviewed") for e in after["matched_required"] + after["matched_preferred"]] == [True]
