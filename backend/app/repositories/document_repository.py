from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    CandidateJobMatch,
    CandidateProfile,
    CandidateSkill,
    CvDocument,
    CvSection,
    ExtractedCandidateTerm,
    ExtractedJobTerm,
    Job,
    JobSection,
    JobSkill,
    ProcessingLog,
)
from app.nlp.skill_extractor import ExtractedTerm
from app.services.section_detection_service import DetectedSection


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create_candidate_profile(self, user_id: UUID) -> CandidateProfile:
        profile = self.db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
        if profile:
            return profile
        profile = CandidateProfile(user_id=user_id)
        self.db.add(profile)
        self.db.flush()
        return profile

    def update_candidate_profile(
        self,
        profile: CandidateProfile,
        headline: str,
        summary: str,
        consent_to_process_cv: bool,
    ) -> CandidateProfile:
        profile.headline = headline
        profile.summary = summary
        profile.consent_to_process_cv = consent_to_process_cv
        self.db.flush()
        return profile

    def create_cv_document(
        self,
        candidate_profile_id: UUID,
        original_filename: str,
        content_type: str,
        source: str,
        raw_text: str,
        cleaned_text: str,
        size_bytes: int,
    ) -> CvDocument:
        document = CvDocument(
            candidate_profile_id=candidate_profile_id,
            original_filename=original_filename,
            content_type=content_type,
            source=source,
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            size_bytes=size_bytes,
            status="processed",
        )
        self.db.add(document)
        self.db.flush()
        return document

    def list_cv_documents(self, candidate_profile_id: UUID) -> list[CvDocument]:
        return list(
            self.db.scalars(
                select(CvDocument)
                .options(selectinload(CvDocument.sections))
                .where(CvDocument.candidate_profile_id == candidate_profile_id)
                .order_by(CvDocument.created_at.desc())
            )
        )

    def get_cv_document(self, document_id: UUID, candidate_profile_id: UUID) -> CvDocument | None:
        return self.db.scalar(
            select(CvDocument)
            .options(selectinload(CvDocument.sections))
            .where(
                CvDocument.id == document_id,
                CvDocument.candidate_profile_id == candidate_profile_id,
            )
        )

    def delete_cv_document(self, document: CvDocument) -> None:
        self.db.delete(document)
        self.db.flush()

    def replace_cv_sections(self, document: CvDocument, sections: list[DetectedSection]) -> None:
        document.sections.clear()
        for section in sections:
            document.sections.append(
                CvSection(
                    section_type=section.section_type,
                    heading=section.heading,
                    content=section.content,
                    start_char=section.start_char,
                    end_char=section.end_char,
                    confidence_score=section.confidence_score,
                    extraction_method=section.extraction_method,
                )
            )
        self.db.flush()

    def replace_candidate_terms(
        self,
        document: CvDocument,
        terms: list[ExtractedTerm],
    ) -> None:
        self.db.query(CandidateSkill).filter(
            CandidateSkill.candidate_profile_id == document.candidate_profile_id,
            CandidateSkill.source == "extraction",
        ).delete(synchronize_session=False)
        self.db.query(ExtractedCandidateTerm).filter(
            ExtractedCandidateTerm.cv_document_id == document.id
        ).delete(synchronize_session=False)
        self.db.flush()

        for term in terms:
            extracted_term = ExtractedCandidateTerm(
                cv_document_id=document.id,
                raw_text=term.raw_text,
                normalized_text=term.normalized_text,
                term_type=term.term_type,
                source_section=term.source_section,
                evidence_sentence=term.evidence_sentence,
                extraction_method=term.extraction_method,
                confidence_score=term.confidence_score,
                start_char=term.start_char,
                end_char=term.end_char,
            )
            self.db.add(extracted_term)
            self.db.flush()
            self.db.add(
                CandidateSkill(
                    candidate_profile_id=document.candidate_profile_id,
                    extracted_term_id=extracted_term.id,
                    raw_text=term.raw_text,
                    normalized_text=term.normalized_text,
                    skill_type=term.term_type,
                    evidence_sentence=term.evidence_sentence,
                    confidence_score=term.confidence_score,
                    review_status="pending",
                )
            )
        self.db.flush()

    def list_candidate_skills(self, candidate_profile_id: UUID) -> list[CandidateSkill]:
        return list(
            self.db.scalars(
                select(CandidateSkill)
                .where(CandidateSkill.candidate_profile_id == candidate_profile_id)
                .order_by(CandidateSkill.normalized_text)
            )
        )

    def list_candidate_skills_for_document(
        self,
        candidate_profile_id: UUID,
        document_id: UUID,
    ) -> list[CandidateSkill]:
        return list(
            self.db.scalars(
                select(CandidateSkill)
                .join(
                    ExtractedCandidateTerm,
                    CandidateSkill.extracted_term_id == ExtractedCandidateTerm.id,
                    isouter=True,
                )
                .where(
                    CandidateSkill.candidate_profile_id == candidate_profile_id,
                    (
                        (ExtractedCandidateTerm.cv_document_id == document_id)
                        | (CandidateSkill.source == "manual_review")
                    ),
                )
                .order_by(CandidateSkill.normalized_text)
            )
        )

    def get_candidate_skill(self, skill_id: UUID, candidate_profile_id: UUID) -> CandidateSkill | None:
        return self.db.scalar(
            select(CandidateSkill).where(
                CandidateSkill.id == skill_id,
                CandidateSkill.candidate_profile_id == candidate_profile_id,
            )
        )

    def create_candidate_skill(
        self,
        candidate_profile_id: UUID,
        raw_text: str,
        normalized_text: str,
        skill_type: str,
        evidence_sentence: str,
        review_status: str,
    ) -> CandidateSkill:
        skill = CandidateSkill(
            candidate_profile_id=candidate_profile_id,
            raw_text=raw_text,
            normalized_text=normalized_text,
            skill_type=skill_type,
            evidence_sentence=evidence_sentence,
            confidence_score=1.0,
            review_status=review_status,
            source="manual_review",
        )
        self.db.add(skill)
        self.db.flush()
        return skill

    def update_candidate_skill(
        self,
        skill: CandidateSkill,
        raw_text: str,
        normalized_text: str,
        skill_type: str,
        evidence_sentence: str,
        review_status: str,
    ) -> CandidateSkill:
        skill.raw_text = raw_text
        skill.normalized_text = normalized_text
        skill.skill_type = skill_type
        skill.evidence_sentence = evidence_sentence
        skill.review_status = review_status
        self.db.flush()
        return skill

    def delete_candidate_skill(self, skill: CandidateSkill) -> None:
        self.db.delete(skill)
        self.db.flush()

    def create_job(
        self,
        title: str,
        company: str,
        location: str,
        employment_type: str,
        description: str,
        cleaned_description: str,
    ) -> Job:
        job = Job(
            title=title,
            company=company,
            location=location,
            employment_type=employment_type,
            description=description,
            cleaned_description=cleaned_description,
            status="processed",
        )
        self.db.add(job)
        self.db.flush()
        return job

    def list_jobs(self, include_archived: bool = False) -> list[Job]:
        statement = select(Job).options(selectinload(Job.sections)).order_by(Job.created_at.desc())
        if not include_archived:
            statement = statement.where(Job.status != "archived")
        return list(self.db.scalars(statement))

    def get_job(self, job_id: UUID) -> Job | None:
        return self.db.scalar(
            select(Job).options(selectinload(Job.sections)).where(Job.id == job_id)
        )

    def update_job(
        self,
        job: Job,
        title: str,
        company: str,
        location: str,
        employment_type: str,
        description: str,
        cleaned_description: str,
        status: str,
    ) -> Job:
        job.title = title
        job.company = company
        job.location = location
        job.employment_type = employment_type
        job.description = description
        job.cleaned_description = cleaned_description
        job.status = status
        self.db.flush()
        return job

    def delete_job(self, job: Job) -> None:
        self.db.delete(job)
        self.db.flush()

    def replace_job_sections(self, job: Job, sections: list[DetectedSection]) -> None:
        job.sections.clear()
        for section in sections:
            job.sections.append(
                JobSection(
                    section_type=section.section_type,
                    heading=section.heading,
                    content=section.content,
                    start_char=section.start_char,
                    end_char=section.end_char,
                    confidence_score=section.confidence_score,
                    extraction_method=section.extraction_method,
                )
            )
        self.db.flush()

    def replace_job_terms(self, job: Job, terms: list[ExtractedTerm]) -> None:
        self.db.query(JobSkill).filter(
            JobSkill.job_id == job.id,
            JobSkill.source == "extraction",
        ).delete(synchronize_session=False)
        self.db.query(ExtractedJobTerm).filter(ExtractedJobTerm.job_id == job.id).delete(
            synchronize_session=False
        )
        self.db.flush()

        for term in terms:
            extracted_term = ExtractedJobTerm(
                job_id=job.id,
                raw_text=term.raw_text,
                normalized_text=term.normalized_text,
                term_type=term.term_type,
                source_section=term.source_section,
                evidence_sentence=term.evidence_sentence,
                extraction_method=term.extraction_method,
                confidence_score=term.confidence_score,
                start_char=term.start_char,
                end_char=term.end_char,
                requirement_type=term.requirement_type,
            )
            self.db.add(extracted_term)
            self.db.flush()
            self.db.add(
                JobSkill(
                    job_id=job.id,
                    extracted_term_id=extracted_term.id,
                    raw_text=term.raw_text,
                    normalized_text=term.normalized_text,
                    skill_type=term.term_type,
                    requirement_type=term.requirement_type,
                    evidence_sentence=term.evidence_sentence,
                    confidence_score=term.confidence_score,
                    review_status="pending",
                )
            )
        self.db.flush()

    def list_job_skills(self, job_id: UUID) -> list[JobSkill]:
        return list(
            self.db.scalars(
                select(JobSkill).where(JobSkill.job_id == job_id).order_by(JobSkill.normalized_text)
            )
        )

    def list_matchable_candidate_skills(self, candidate_profile_id: UUID) -> list[CandidateSkill]:
        return list(
            self.db.scalars(
                select(CandidateSkill)
                .where(
                    CandidateSkill.candidate_profile_id == candidate_profile_id,
                    CandidateSkill.review_status != "rejected",
                )
                .order_by(CandidateSkill.normalized_text)
            )
        )

    def list_matchable_job_skills(self, job_id: UUID) -> list[JobSkill]:
        return list(
            self.db.scalars(
                select(JobSkill)
                .where(
                    JobSkill.job_id == job_id,
                    JobSkill.review_status != "rejected",
                )
                .order_by(JobSkill.normalized_text)
            )
        )

    def upsert_candidate_job_match(
        self,
        candidate_profile_id: UUID,
        job_id: UUID,
        score: float,
        matched_required: list[str],
        matched_preferred: list[str],
        missing_required: list[str],
        missing_preferred: list[str],
        candidate_skill_count: int,
        job_skill_count: int,
        explanation: str,
    ) -> CandidateJobMatch:
        match = self.db.scalar(
            select(CandidateJobMatch).where(
                CandidateJobMatch.candidate_profile_id == candidate_profile_id,
                CandidateJobMatch.job_id == job_id,
            )
        )
        if match is None:
            match = CandidateJobMatch(candidate_profile_id=candidate_profile_id, job_id=job_id)
            self.db.add(match)
        match.score = score
        match.matched_required = matched_required
        match.matched_preferred = matched_preferred
        match.missing_required = missing_required
        match.missing_preferred = missing_preferred
        match.candidate_skill_count = candidate_skill_count
        match.job_skill_count = job_skill_count
        match.explanation = explanation
        self.db.flush()
        return match

    def list_candidate_job_matches(self, candidate_profile_id: UUID) -> list[CandidateJobMatch]:
        return list(
            self.db.scalars(
                select(CandidateJobMatch)
                .options(selectinload(CandidateJobMatch.job))
                .where(CandidateJobMatch.candidate_profile_id == candidate_profile_id)
                .order_by(CandidateJobMatch.score.desc(), CandidateJobMatch.updated_at.desc())
            )
        )

    def get_job_skill(self, skill_id: UUID, job_id: UUID) -> JobSkill | None:
        return self.db.scalar(
            select(JobSkill).where(
                JobSkill.id == skill_id,
                JobSkill.job_id == job_id,
            )
        )

    def update_job_skill(
        self,
        skill: JobSkill,
        raw_text: str,
        normalized_text: str,
        skill_type: str,
        requirement_type: str,
        evidence_sentence: str,
        review_status: str,
    ) -> JobSkill:
        skill.raw_text = raw_text
        skill.normalized_text = normalized_text
        skill.skill_type = skill_type
        skill.requirement_type = requirement_type
        skill.evidence_sentence = evidence_sentence
        skill.review_status = review_status
        self.db.flush()
        return skill

    def add_processing_log(
        self,
        entity_type: str,
        entity_id: UUID,
        stage: str,
        status: str,
        message: str,
        metadata_json: dict | None = None,
    ) -> ProcessingLog:
        log = ProcessingLog(
            entity_type=entity_type,
            entity_id=entity_id,
            stage=stage,
            status=status,
            message=message,
            metadata_json=metadata_json or {},
        )
        self.db.add(log)
        self.db.flush()
        return log

    def list_processing_logs(self, entity_type: str | None = None) -> list[ProcessingLog]:
        statement = select(ProcessingLog).order_by(ProcessingLog.created_at.desc())
        if entity_type:
            statement = statement.where(ProcessingLog.entity_type == entity_type)
        return list(self.db.scalars(statement))
