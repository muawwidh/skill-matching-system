from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import CandidateJobMatch, Job, User
from app.repositories.document_repository import DocumentRepository


@dataclass(frozen=True)
class SkillSets:
    candidate: set[str]
    required: set[str]
    preferred: set[str]
    unknown: set[str]


class MatchingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DocumentRepository(db)

    def refresh_my_recommendations(self, user: User) -> list[CandidateJobMatch]:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        jobs = self.repository.list_jobs(include_archived=False)
        for job in jobs:
            self._score_job(profile.id, job)
        self.repository.add_processing_log(
            "candidate_profile",
            profile.id,
            "job_matching",
            "success",
            f"Refreshed matches for {len(jobs)} jobs.",
            {"job_count": len(jobs)},
        )
        self.db.commit()
        return self.repository.list_candidate_job_matches(profile.id)

    def match_my_job(self, user: User, job_id: UUID) -> CandidateJobMatch:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        job = self.repository.get_job(job_id)
        if not job or job.status == "archived":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        match = self._score_job(profile.id, job)
        self.repository.add_processing_log(
            "job",
            job.id,
            "job_matching",
            "success",
            f"Calculated match score {round(match.score)} for {job.title}.",
            {"score": match.score},
        )
        self.db.commit()
        self.db.refresh(match)
        return match

    def list_my_recommendations(self, user: User) -> list[CandidateJobMatch]:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        existing_matches = self.repository.list_candidate_job_matches(profile.id)
        active_job_ids = {job.id for job in self.repository.list_jobs(include_archived=False)}
        if active_job_ids and {match.job_id for match in existing_matches} >= active_job_ids:
            return [match for match in existing_matches if match.job_id in active_job_ids]
        return self.refresh_my_recommendations(user)

    def _score_job(self, candidate_profile_id: UUID, job: Job) -> CandidateJobMatch:
        skill_sets = self._skill_sets(candidate_profile_id, job.id)
        required_pool = skill_sets.required | skill_sets.unknown
        preferred_pool = skill_sets.preferred

        matched_required = sorted(required_pool & skill_sets.candidate)
        matched_preferred = sorted(preferred_pool & skill_sets.candidate)
        missing_required = sorted(required_pool - skill_sets.candidate)
        missing_preferred = sorted(preferred_pool - skill_sets.candidate)

        required_weight = 2
        preferred_weight = 1
        total_weight = (len(required_pool) * required_weight) + (len(preferred_pool) * preferred_weight)
        matched_weight = (len(matched_required) * required_weight) + (
            len(matched_preferred) * preferred_weight
        )
        score = round((matched_weight / total_weight) * 100, 2) if total_weight else 0.0
        explanation = self._explanation(score, matched_required, missing_required, missing_preferred)

        return self.repository.upsert_candidate_job_match(
            candidate_profile_id=candidate_profile_id,
            job_id=job.id,
            score=score,
            matched_required=matched_required,
            matched_preferred=matched_preferred,
            missing_required=missing_required,
            missing_preferred=missing_preferred,
            candidate_skill_count=len(skill_sets.candidate),
            job_skill_count=len(required_pool | preferred_pool),
            explanation=explanation,
        )

    def _skill_sets(self, candidate_profile_id: UUID, job_id: UUID) -> SkillSets:
        candidate_skills = self.repository.list_matchable_candidate_skills(candidate_profile_id)
        job_skills = self.repository.list_matchable_job_skills(job_id)
        return SkillSets(
            candidate={
                skill.normalized_text for skill in candidate_skills if self._is_matchable_type(skill.skill_type)
            },
            required={
                skill.normalized_text
                for skill in job_skills
                if self._is_matchable_type(skill.skill_type) and skill.requirement_type == "required"
            },
            preferred={
                skill.normalized_text
                for skill in job_skills
                if self._is_matchable_type(skill.skill_type) and skill.requirement_type == "preferred"
            },
            unknown={
                skill.normalized_text
                for skill in job_skills
                if self._is_matchable_type(skill.skill_type) and skill.requirement_type == "unknown"
            },
        )

    @staticmethod
    def _is_matchable_type(skill_type: str) -> bool:
        return skill_type in {"skill", "tool"}

    @staticmethod
    def _explanation(
        score: float,
        matched_required: list[str],
        missing_required: list[str],
        missing_preferred: list[str],
    ) -> str:
        if not matched_required and missing_required:
            return "Low match because required skills are currently missing from the candidate profile."
        if score >= 80:
            return "Strong match based on required skill coverage."
        if score >= 50:
            return "Partial match with some important gaps to close."
        if missing_preferred and not missing_required:
            return "Required skills are mostly covered, but preferred skills could improve the match."
        return "Limited match based on the skills currently extracted and reviewed."
