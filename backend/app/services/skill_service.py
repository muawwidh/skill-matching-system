from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import CandidateSkill, JobSkill, User
from app.repositories.document_repository import DocumentRepository
from app.schemas.documents import CandidateSkillReviewRequest, JobSkillUpdate


class SkillService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DocumentRepository(db)

    def list_my_candidate_skills(self, user: User) -> list[CandidateSkill]:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        self.db.commit()
        return self.repository.list_candidate_skills(profile.id)

    def list_my_cv_skills(self, user: User, document_id: UUID) -> list[CandidateSkill]:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        document = self.repository.get_cv_document(document_id, profile.id)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")
        return self.repository.list_candidate_skills_for_document(profile.id, document_id)

    def review_my_candidate_skills(
        self,
        user: User,
        payload: CandidateSkillReviewRequest,
    ) -> list[CandidateSkill]:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        submitted_ids = {item.id for item in payload.skills if item.id}
        existing_skills = {skill.id: skill for skill in self.repository.list_candidate_skills(profile.id)}

        for skill_id, skill in existing_skills.items():
            if skill_id not in submitted_ids and skill.source == "manual_review":
                self.repository.delete_candidate_skill(skill)

        for item in payload.skills:
            if item.id:
                skill = existing_skills.get(item.id)
                if not skill:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found.")
                self.repository.update_candidate_skill(
                    skill=skill,
                    raw_text=item.raw_text,
                    normalized_text=item.normalized_text.lower(),
                    skill_type=item.skill_type,
                    evidence_sentence=item.evidence_sentence,
                    review_status=item.review_status,
                )
            else:
                self.repository.create_candidate_skill(
                    candidate_profile_id=profile.id,
                    raw_text=item.raw_text,
                    normalized_text=item.normalized_text.lower(),
                    skill_type=item.skill_type,
                    evidence_sentence=item.evidence_sentence,
                    review_status=item.review_status,
                )

        self.repository.add_processing_log(
            "candidate_profile",
            profile.id,
            "skill_review",
            "success",
            f"Reviewed {len(payload.skills)} candidate skills.",
            {"skill_count": len(payload.skills)},
        )
        self.db.commit()
        return self.repository.list_candidate_skills(profile.id)

    def list_job_skills(self, job_id: UUID) -> list[JobSkill]:
        if not self.repository.get_job(job_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return self.repository.list_job_skills(job_id)

    def update_job_skill(self, job_id: UUID, skill_id: UUID, payload: JobSkillUpdate) -> JobSkill:
        if not self.repository.get_job(job_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        skill = self.repository.get_job_skill(skill_id, job_id)
        if not skill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job skill not found.")
        updated = self.repository.update_job_skill(
            skill=skill,
            raw_text=payload.raw_text,
            normalized_text=payload.normalized_text.lower(),
            skill_type=payload.skill_type,
            requirement_type=payload.requirement_type,
            evidence_sentence=payload.evidence_sentence,
            review_status=payload.review_status,
        )
        self.repository.add_processing_log(
            "job",
            job_id,
            "job_skill_review",
            "success",
            f"Reviewed job skill {updated.normalized_text}.",
            {"skill_id": str(updated.id)},
        )
        self.db.commit()
        self.db.refresh(updated)
        return updated
