import json
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import CandidateSkill, JobSkill, User
from app.repositories.document_repository import DocumentRepository
from app.schemas.documents import (CandidateSkillRead, CandidateSkillGroup, CandidateSkillTaxonomy, EscoAreaRead, ManualSkillRead,
                                   CandidateSkillReviewRequest, JobSkillUpdate)


MANUAL_SOURCE = "manual_review"  # skills the candidate added by hand


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
        document_id: UUID | None = None,
    ) -> list[CandidateSkill]:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        submitted_ids = {item.id for item in payload.skills if item.id}
        skills = (self.list_my_cv_skills(user, document_id) if document_id else
                  self.repository.list_candidate_skills(profile.id))
        existing_skills = {skill.id: skill for skill in skills}
        if not submitted_ids <= existing_skills.keys():
            raise HTTPException(status_code=404, detail="Skill not found.")

        # Skills added by hand are only removed through remove_my_manual_skill, never by leaving them out here.

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
        return (self.list_my_cv_skills(user, document_id) if document_id else
                self.repository.list_candidate_skills(profile.id))

    def add_my_manual_skill(self, user: User, label: str) -> CandidateSkill:
        """Add a skill by hand (approved, not tied to a CV). The same skill twice is refused."""
        profile = self.repository.get_or_create_candidate_profile(user.id)
        text = " ".join(label.split())
        normalized = text.lower()
        if any(skill.source == MANUAL_SOURCE and skill.normalized_text == normalized
               for skill in self.repository.list_candidate_skills(profile.id)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already added this skill.")
        skill = self.repository.create_candidate_skill(
            candidate_profile_id=profile.id, raw_text=text, normalized_text=normalized, skill_type="skill",
            evidence_sentence="", review_status="approved")
        self.repository.add_processing_log("candidate_profile", profile.id, "skill_review", "success",
                                           "Added a skill by hand.", {"skill_count": 1})
        self.db.commit()
        return skill

    def remove_my_manual_skill(self, user: User, skill_id: UUID) -> None:
        """Remove one skill the candidate added by hand. CV skills cannot be removed here."""
        profile = self.repository.get_or_create_candidate_profile(user.id)
        skill = next((item for item in self.repository.list_candidate_skills(profile.id)
                      if item.id == skill_id and item.source == MANUAL_SOURCE), None)
        if skill is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found.")
        self.repository.delete_candidate_skill(skill)
        self.repository.add_processing_log("candidate_profile", profile.id, "skill_review", "success",
                                           "Removed a skill added by hand.", {"skill_count": 1})
        self.db.commit()

    def my_manual_skills(self, user: User) -> list[ManualSkillRead]:
        """Skills added by hand, each with its ESCO area when it has an approved link (display only)."""
        skills = [skill for skill in self.list_my_candidate_skills(user) if skill.source == MANUAL_SOURCE]
        concepts = self.repository.approved_skill_concepts("candidate", skills)
        areas = self.repository.esco_areas({concept for concept, _ in concepts.values()})
        result = []
        for skill in skills:
            area = areas.get(concepts[skill.id][0]) if skill.id in concepts else None
            result.append(ManualSkillRead.model_validate(skill).model_copy(
                update={"esco_area": EscoAreaRead(code=area[0], label=area[1]) if area else None}))
        return result

    def grouped_cv_skills(self, user: User, document_id: UUID) -> list[CandidateSkillGroup]:
        skills = self.list_my_cv_skills(user, document_id)
        identities = self.repository.candidate_skill_taxonomies(skills)
        groups: dict[str, CandidateSkillGroup] = {}
        for skill in skills:
            taxonomy = None
            identity = identities.get(skill.extracted_term_id)
            if identity:
                concept, term = identity
                # Pre-existing corrections may still refer to an old extracted term.
                if (skill.raw_text, skill.normalized_text, skill.skill_type) == (
                        term.raw_text, term.normalized_text, term.term_type):
                    release = concept.taxonomy_version
                    taxonomy = CandidateSkillTaxonomy(concept_id=concept.id, release_id=release.id,
                        external_id=concept.external_id, preferred_label=concept.preferred_label,
                        source=release.source.code, version=release.version)
            # Match the existing extraction/save normalization, without fuzzy/alias equivalence.
            key = (f"taxonomy:{taxonomy.release_id}:{taxonomy.concept_id}" if taxonomy else
                   "unlinked:" + json.dumps([skill.skill_type, skill.normalized_text.lower()]))
            if key not in groups:
                groups[key] = CandidateSkillGroup(key=key,
                    label=taxonomy.preferred_label if taxonomy else skill.normalized_text,
                    taxonomy=taxonomy, occurrences=[])
            groups[key].occurrences.append(CandidateSkillRead.model_validate(skill))
        # ESCO area for the profile's skill map (display only).
        areas = self.repository.esco_areas({g.taxonomy.concept_id for g in groups.values() if g.taxonomy})
        for group in groups.values():
            area = areas.get(group.taxonomy.concept_id) if group.taxonomy else None
            if area:
                group.esco_area = EscoAreaRead(code=area[0], label=area[1])
        return list(groups.values())

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
        requested = (payload.raw_text, payload.normalized_text.lower(), payload.skill_type,
                     payload.requirement_type, payload.evidence_sentence, payload.review_status)
        current = (skill.raw_text, skill.normalized_text, skill.skill_type,
                   skill.requirement_type, skill.evidence_sentence, skill.review_status)
        if current == requested:
            return skill
        updated = self.repository.update_job_skill(
            skill=skill,
            raw_text=payload.raw_text,
            normalized_text=requested[1],
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
