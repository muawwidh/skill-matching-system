"""Relevance (D060): same 3-digit ISCO group, merged periods, summed months; when the line is shown."""
from datetime import date

from app.db.models import CandidateWorkEntry, Job
from app.services.experience_service import ExperienceService
from tests.esco_occupations import add_esco_occupations

TODAY = date(2026, 11, 21)


def _profile(db, client):
    from tests.test_recommendations import register
    from app.db.models import CandidateProfile, User
    from sqlalchemy import select
    register(client, "candidate@example.com")
    user = db.scalar(select(User).where(User.email == "candidate@example.com"))
    profile = CandidateProfile(user_id=user.id, consent_to_process_cv=True)
    db.add(profile)
    db.commit()
    return profile


def _entry(db, profile, occupation, start, end):
    db.add(CandidateWorkEntry(candidate_profile_id=profile.id, title="t", start_month=start, end_month=end,
                              occupation_concept_id=occupation.id if occupation else None, source="manual"))
    db.commit()


def _job(title, text="Requirements\\n- 3+ years of experience with Python", source="arbeitnow"):
    return Job(title=title, description=text, cleaned_description=text, status="processed", source=source,
               content_hash=title)


def test_relevant_months_merge_periods_in_the_same_isco_group(client, db_session):
    occ = add_esco_occupations(db_session)
    profile = _profile(db_session, client)
    _entry(db_session, profile, occ["data scientist"], date(2018, 1, 1), date(2019, 12, 1))       # 2511 -> 251
    _entry(db_session, profile, occ["software developer"], date(2019, 7, 1), date(2020, 6, 1))   # 2512, overlaps
    _entry(db_session, profile, occ["cloud devops engineer"], date(2026, 1, 1), None)            # 2512 via parent, present
    _entry(db_session, profile, occ["database administrator"], date(2010, 1, 1), date(2015, 12, 1))  # 252: other group
    _entry(db_session, profile, None, date(2000, 1, 1), date(2009, 12, 1))                      # no occupation: ignored
    service = ExperienceService(db_session, today=TODAY)
    periods = service.candidate_periods(profile.id)
    assert len(periods) == 4
    software = service.job_occupation(_job("Software Engineer"))
    assert service.relevant_months(periods, software["isco_code"]) == 30 + 11  # Jan 2018-Jun 2020, Jan-Nov 2026
    assessment = service.assess(_job("Software Engineer"), software, periods)
    assert assessment == {"relevant_months": 41, "relevant_years": 3.0, "isco_group": "251",
                          "isco_group_label": "Software and applications developers and analysts",
                          "min_required_years": 3, "meets_requirement": True}
    dba = service.job_occupation(_job("Database Administrator"))
    below = service.assess(_job("Database Administrator", "- 7+ years of experience as a DBA"), dba, periods)
    assert below["relevant_months"] == 72 and below["min_required_years"] == 7 and below["meets_requirement"] is False


def test_assessment_needs_a_minimum_an_occupation_and_entries(client, db_session):
    occ = add_esco_occupations(db_session)
    profile = _profile(db_session, client)
    service = ExperienceService(db_session, today=TODAY)
    software = service.job_occupation(_job("Software Engineer"))
    assert service.assess(_job("Software Engineer"), software, []) is None  # no entries with an occupation
    _entry(db_session, profile, occ["software developer"], date(2020, 1, 1), date(2020, 12, 1))
    periods = service.candidate_periods(profile.id)
    assert service.assess(_job("Software Engineer", "We build tools."), software, periods) is None  # no minimum
    wizard = _job("Office Wizard")
    assert service.assess(wizard, service.job_occupation(wizard), periods) is None  # occupation not determined
    evaluation = _job("Software Engineer", source="evaluation")
    assert service.assess(evaluation, service.job_occupation(evaluation), periods) is None
    unrelated = service.assess(_job("Sales Manager", "- 1+ year of experience in sales"),
                               service.job_occupation(_job("Sales Manager")), periods)
    assert unrelated["relevant_months"] == 0 and unrelated["meets_requirement"] is False
