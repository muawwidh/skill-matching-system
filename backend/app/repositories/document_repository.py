from collections import Counter, defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.db.models import (
    ApprovedTaxonomyLink,
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
    Role,
    TaxonomyLinkCandidate,
    TaxonomyConcept,
    User,
)
from app.db.models.taxonomy import TaxonomyReviewEvent
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
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_profile(document.candidate_profile_id)
        term_ids = list(
            self.db.scalars(
                select(ExtractedCandidateTerm.id).where(
                    ExtractedCandidateTerm.cv_document_id == document.id
                )
            )
        )
        self._delete_extraction_skills(term_ids)
        self._delete_taxonomy_links("candidate", term_ids)
        self.db.delete(document)
        self.db.flush()

    def delete_candidate_profile_data(self, profile: CandidateProfile) -> dict[str, int]:
        """Erase everything derived from one candidate profile (account deletion).

        Deletes embeddings, skills (extracted and manual), taxonomy
        link suggestions, selected links and their review events, processing
        logs, extracted terms, CV sections and CVs, then the profile. Deletes are
        explicit, so the result does not depend on database cascade settings.
        Returns row counts per kind.
        """
        from app.db.models import CandidateProfileEmbedding

        documents = list(self.db.scalars(select(CvDocument.id).where(
            CvDocument.candidate_profile_id == profile.id)))
        term_ids = list(self.db.scalars(select(ExtractedCandidateTerm.id).where(
            ExtractedCandidateTerm.cv_document_id.in_(documents)))) if documents else []
        counts: dict[str, int] = {}

        def delete(name: str, model, *where) -> None:
            counts[name] = self.db.query(model).filter(*where).delete(synchronize_session=False)

        delete("embeddings", CandidateProfileEmbedding, CandidateProfileEmbedding.candidate_profile_id == profile.id)
        delete("skills", CandidateSkill, CandidateSkill.candidate_profile_id == profile.id)
        if term_ids:
            delete("selected_links", ApprovedTaxonomyLink, ApprovedTaxonomyLink.term_source == "candidate",
                   ApprovedTaxonomyLink.extracted_term_id.in_(term_ids))
            delete("link_suggestions", TaxonomyLinkCandidate, TaxonomyLinkCandidate.term_source == "candidate",
                   TaxonomyLinkCandidate.extracted_term_id.in_(term_ids))
            delete("link_review_events", TaxonomyReviewEvent, TaxonomyReviewEvent.term_source == "candidate",
                   TaxonomyReviewEvent.extracted_term_id.in_(term_ids))
            delete("extracted_terms", ExtractedCandidateTerm, ExtractedCandidateTerm.id.in_(term_ids))
        delete("processing_logs", ProcessingLog,
               ((ProcessingLog.entity_type == "candidate_profile") & (ProcessingLog.entity_id == profile.id))
               | ((ProcessingLog.entity_type == "cv_document") & ProcessingLog.entity_id.in_(documents or [profile.id])))
        if documents:
            delete("cv_sections", CvSection, CvSection.cv_document_id.in_(documents))
            delete("cvs", CvDocument, CvDocument.id.in_(documents))
        self.db.delete(profile)
        self.db.flush()
        return counts

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
    ) -> list[UUID]:
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_profile(document.candidate_profile_id)
        previous_terms = list(
            self.db.scalars(
                select(ExtractedCandidateTerm).where(
                    ExtractedCandidateTerm.cv_document_id == document.id
                )
            )
        )
        previous_ids = [term.id for term in previous_terms]
        skills = list(self.db.scalars(select(CandidateSkill).where(
            CandidateSkill.extracted_term_id.in_(previous_ids),
            CandidateSkill.source == "extraction",
        ))) if previous_ids else []
        skills_by_term = {skill.extracted_term_id: skill for skill in skills}
        previous_by_key: dict[tuple, list[ExtractedCandidateTerm]] = defaultdict(list)
        for previous in previous_terms:
            if previous.id in skills_by_term:
                previous_by_key[self._occurrence_key(previous)].append(previous)
        incoming_counts = Counter(self._occurrence_key(term) for term in terms)
        retained_ids = {
            previous_by_key[key][0].id
            for key, count in incoming_counts.items()
            if count == 1 and len(previous_by_key[key]) == 1
        }
        removed_ids = [term_id for term_id in previous_ids if term_id not in retained_ids]
        self._delete_extraction_skills(removed_ids)
        self._delete_taxonomy_links("candidate", removed_ids)
        if removed_ids:
            self.db.query(ExtractedCandidateTerm).filter(
                ExtractedCandidateTerm.id.in_(removed_ids)
            ).delete(synchronize_session=False)
            self.db.flush()

        created_ids: list[UUID] = []
        for term in terms:
            key = self._occurrence_key(term)
            if incoming_counts[key] == 1 and len(previous_by_key[key]) == 1:
                continue
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
            created_ids.append(extracted_term.id)
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
        linked_ids = set(self.db.scalars(select(TaxonomyLinkCandidate.extracted_term_id).where(
            TaxonomyLinkCandidate.term_source == "candidate",
            TaxonomyLinkCandidate.extracted_term_id.in_(retained_ids),
        ))) if retained_ids else set()
        linked_ids.update(self.db.scalars(select(ApprovedTaxonomyLink.extracted_term_id).where(
            ApprovedTaxonomyLink.term_source == "candidate",
            ApprovedTaxonomyLink.extracted_term_id.in_(retained_ids),
        )))
        return created_ids + sorted(retained_ids - linked_ids)

    @staticmethod
    def _occurrence_key(term: ExtractedCandidateTerm | ExtractedTerm) -> tuple:
        return (
            term.raw_text, term.normalized_text, term.term_type, term.source_section,
            term.evidence_sentence, term.extraction_method, term.confidence_score,
            term.start_char, term.end_char,
        )

    def _delete_extraction_skills(self, term_ids: list[UUID]) -> None:
        if term_ids:
            self.db.query(CandidateSkill).filter(
                CandidateSkill.extracted_term_id.in_(term_ids),
                CandidateSkill.source == "extraction",
            ).delete(synchronize_session=False)

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

    def candidate_skill_status_counts(self, candidate_profile_id: UUID) -> list[tuple[UUID | None, str, str, int]]:
        """(CV document ID or None, skill source, review status, count) for one profile."""
        return [tuple(row) for row in self.db.execute(
            select(ExtractedCandidateTerm.cv_document_id, CandidateSkill.source,
                   CandidateSkill.review_status, func.count())
            .select_from(CandidateSkill)
            .join(ExtractedCandidateTerm, CandidateSkill.extracted_term_id == ExtractedCandidateTerm.id,
                  isouter=True)
            .where(CandidateSkill.candidate_profile_id == candidate_profile_id)
            .group_by(ExtractedCandidateTerm.cv_document_id, CandidateSkill.source, CandidateSkill.review_status)
        ).all()]

    def get_candidate_skill(self, skill_id: UUID, candidate_profile_id: UUID) -> CandidateSkill | None:
        return self.db.scalar(
            select(CandidateSkill).where(
                CandidateSkill.id == skill_id,
                CandidateSkill.candidate_profile_id == candidate_profile_id,
            )
        )

    def candidate_skill_taxonomies(
        self, skills: list[CandidateSkill]
    ) -> dict[UUID, tuple[TaxonomyConcept, ExtractedCandidateTerm]]:
        term_ids = [skill.extracted_term_id for skill in skills if skill.extracted_term_id]
        if not term_ids:
            return {}
        rows = self.db.execute(select(ApprovedTaxonomyLink, ExtractedCandidateTerm).join(
            ExtractedCandidateTerm, ExtractedCandidateTerm.id == ApprovedTaxonomyLink.extracted_term_id
        ).where(ApprovedTaxonomyLink.term_source == "candidate",
                ApprovedTaxonomyLink.extracted_term_id.in_(term_ids)))
        return {term.id: (link.concept, term) for link, term in rows}

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
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_profile(candidate_profile_id)
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
        if skill.extracted_term_id and (skill.raw_text, skill.normalized_text, skill.skill_type) != (
                raw_text, normalized_text, skill_type):
            # A correction invalidates this occurrence's mapping, not its evidence or audit history.
            from app.repositories.taxonomy_repository import TaxonomyRepository

            TaxonomyRepository(self.db).replace_link_candidates("candidate", skill.extracted_term_id)
            term = self.db.get(ExtractedCandidateTerm, skill.extracted_term_id)
            if term:
                term.raw_text = raw_text
                term.normalized_text = normalized_text
                term.term_type = skill_type
        skill.raw_text = raw_text
        skill.normalized_text = normalized_text
        skill.skill_type = skill_type
        skill.evidence_sentence = evidence_sentence
        skill.review_status = review_status
        self.db.flush()
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_profile(skill.candidate_profile_id)
        return skill

    def delete_candidate_skill(self, skill: CandidateSkill) -> None:
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_profile(skill.candidate_profile_id)
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
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_job(job.id)
        return job

    def delete_job(self, job: Job) -> None:
        term_ids = list(
            self.db.scalars(
                select(ExtractedJobTerm.id).where(ExtractedJobTerm.job_id == job.id)
            )
        )
        self._delete_taxonomy_links("job", term_ids)
        self.db.delete(job)
        self.db.flush()

    def _delete_taxonomy_links(self, term_source: str, term_ids: list[UUID]) -> None:
        if not term_ids:
            return
        self.db.query(ApprovedTaxonomyLink).filter(
            ApprovedTaxonomyLink.term_source == term_source,
            ApprovedTaxonomyLink.extracted_term_id.in_(term_ids),
        ).delete(synchronize_session=False)
        self.db.query(TaxonomyLinkCandidate).filter(
            TaxonomyLinkCandidate.term_source == term_source,
            TaxonomyLinkCandidate.extracted_term_id.in_(term_ids),
        ).delete(synchronize_session=False)

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
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_job(job.id)
        previous_term_ids = list(
            self.db.scalars(
                select(ExtractedJobTerm.id).where(ExtractedJobTerm.job_id == job.id)
            )
        )
        if previous_term_ids:
            self.db.query(ApprovedTaxonomyLink).filter(
                ApprovedTaxonomyLink.term_source == "job",
                ApprovedTaxonomyLink.extracted_term_id.in_(previous_term_ids),
            ).delete(synchronize_session=False)
            self.db.query(TaxonomyLinkCandidate).filter(
                TaxonomyLinkCandidate.term_source == "job",
                TaxonomyLinkCandidate.extracted_term_id.in_(previous_term_ids),
            ).delete(synchronize_session=False)
        self.db.query(JobSkill).filter(
            JobSkill.job_id == job.id,
            JobSkill.source == "extraction",
        ).delete(synchronize_session=False)
        self.db.query(ExtractedJobTerm).filter(ExtractedJobTerm.job_id == job.id).delete(
            synchronize_session=False
        )
        self.db.flush()
        self.add_job_terms(job, terms)

    def add_job_terms(self, job: Job, terms: list[ExtractedTerm]) -> list[UUID]:
        """Insert extracted terms, each with a pending job skill; returns the new term IDs."""
        term_ids: list[UUID] = []
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
            term_ids.append(extracted_term.id)
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
        return term_ids

    def job_extraction_state(self, job_id: UUID) -> list[tuple[ExtractedJobTerm, JobSkill | None]]:
        """Stored extracted terms of a job with their (extraction-sourced) job skill, if any."""
        skills = {
            skill.extracted_term_id: skill
            for skill in self.db.scalars(select(JobSkill).where(JobSkill.job_id == job_id, JobSkill.extracted_term_id.is_not(None)))
        }
        terms = self.db.scalars(
            select(ExtractedJobTerm).where(ExtractedJobTerm.job_id == job_id).order_by(ExtractedJobTerm.start_char)
        )
        return [(term, skills.get(term.id)) for term in terms]

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
                    CandidateSkill.review_status == "approved",
                )
                .order_by(CandidateSkill.normalized_text, CandidateSkill.id)
            )
        )

    def list_matchable_job_skills(self, job_id: UUID, include_unreviewed: bool = False) -> list[JobSkill]:
        """Approved job skills; with `include_unreviewed` also pending ones. Rejected never (D054)."""
        statuses = ("approved", "pending") if include_unreviewed else ("approved",)
        return list(
            self.db.scalars(
                select(JobSkill)
                .where(
                    JobSkill.job_id == job_id,
                    JobSkill.review_status.in_(statuses),
                )
                .order_by(JobSkill.normalized_text, JobSkill.id)
            )
        )

    def specific_esco_broader_concepts(self, concept_ids: set[UUID]) -> dict[UUID, dict[UUID, str]]:
        """Direct ESCO broader concepts that are themselves skills or knowledge (D050).

        Maps each given concept to {broader concept ID: preferred label}. Broader
        ESCO skill groups are left out on purpose: they are wide (median 13,
        up to 217 member skills in ESCO 1.2.1) and would overstate similarity.
        Only relationships in the concept's own active release are used.
        """
        from app.db.models import TaxonomyRelationship, TaxonomySource, TaxonomyVersion

        if not concept_ids:
            return {}
        broader = aliased(TaxonomyConcept)
        rows = self.db.execute(
            select(TaxonomyRelationship.source_concept_id, broader.id, broader.preferred_label)
            .join(broader, broader.id == TaxonomyRelationship.target_concept_id)
            .join(TaxonomyVersion, TaxonomyVersion.id == TaxonomyRelationship.taxonomy_version_id)
            .join(TaxonomySource, TaxonomySource.id == TaxonomyVersion.source_id)
            .where(
                TaxonomyRelationship.source_concept_id.in_(concept_ids),
                TaxonomyRelationship.relationship_type == "broader",
                TaxonomySource.code == "ESCO",
                TaxonomyVersion.status == "active",
                broader.concept_type.in_(("skill", "knowledge")),
            )
        ).all()
        result: dict[UUID, dict[UUID, str]] = {}
        for child, parent, label in rows:
            result.setdefault(child, {})[parent] = label
        return result

    def approved_skill_concepts(
        self, term_source: str, skills: list[CandidateSkill] | list[JobSkill]
    ) -> dict[UUID, tuple[UUID, str]]:
        """Map skill IDs to (concept ID, preferred label) for approved links on active releases.

        A link is ignored when the skill text no longer equals its extracted term,
        mirroring the consistency rule used for retrieval representations.
        """
        term_ids = [skill.extracted_term_id for skill in skills if skill.extracted_term_id]
        if not term_ids:
            return {}
        links = {
            link.extracted_term_id: link
            for link in self.db.scalars(
                select(ApprovedTaxonomyLink).where(
                    ApprovedTaxonomyLink.term_source == term_source,
                    ApprovedTaxonomyLink.extracted_term_id.in_(term_ids),
                )
            )
            if link.concept.taxonomy_version.status == "active"
        }
        term_model = ExtractedCandidateTerm if term_source == "candidate" else ExtractedJobTerm
        result: dict[UUID, tuple[UUID, str]] = {}
        for skill in skills:
            link = links.get(skill.extracted_term_id)
            if link is None:
                continue
            term = self.db.get(term_model, skill.extracted_term_id)
            if not term or (skill.raw_text, skill.normalized_text, skill.skill_type) != (
                term.raw_text, term.normalized_text, term.term_type
            ):
                continue
            result[skill.id] = (link.concept_id, link.concept.preferred_label)
        return result

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
        current = (skill.raw_text, skill.normalized_text, skill.skill_type,
                   skill.requirement_type, skill.evidence_sentence, skill.review_status)
        requested = (raw_text, normalized_text, skill_type, requirement_type,
                     evidence_sentence, review_status)
        if current == requested:
            return skill
        if current[:3] != requested[:3] and skill.extracted_term_id:
            from app.repositories.taxonomy_repository import TaxonomyRepository

            term = self.db.get(ExtractedJobTerm, skill.extracted_term_id)
            if term is None or term.job_id != skill.job_id:
                raise ValueError("Job skill extraction term is missing or belongs to another job.")
            TaxonomyRepository(self.db).replace_link_candidates("job", term.id)
            term.raw_text = raw_text
            term.normalized_text = normalized_text
            term.term_type = skill_type
        skill.raw_text = raw_text
        skill.normalized_text = normalized_text
        skill.skill_type = skill_type
        skill.requirement_type = requirement_type
        skill.evidence_sentence = evidence_sentence
        skill.review_status = review_status
        self.db.flush()
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_job(skill.job_id)
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

    # --- Read-only counts for the administrator system overview -------------------------

    def count_users_with_role(self, role_name: str) -> int:
        return self.db.scalar(
            select(func.count(func.distinct(User.id))).join(User.roles).where(Role.name == role_name)
        ) or 0

    def count_by(self, column, *where) -> dict[str, int]:
        """Row counts grouped by one column, e.g. `count_by(Job.status)`."""
        return {key: count for key, count in self.db.execute(
            select(column, func.count()).where(*where).group_by(column)
        ).all()}

    def taxonomy_link_coverage(self, term_source: str) -> dict[str, int]:
        """Approved skills split by taxonomy-link state: approved, pending suggestion, or none.

        "approved" uses the same rule as matching and retrieval: an approved link on an
        active release whose term text still equals the skill text.
        """
        model = CandidateSkill if term_source == "candidate" else JobSkill
        skills = list(self.db.scalars(select(model).where(model.review_status == "approved")))
        linked = self.approved_skill_concepts(term_source, skills)
        unlinked_terms = {s.extracted_term_id for s in skills if s.id not in linked and s.extracted_term_id}
        pending_terms = set(self.db.scalars(
            select(TaxonomyLinkCandidate.extracted_term_id).where(
                TaxonomyLinkCandidate.term_source == term_source,
                TaxonomyLinkCandidate.review_status == "pending",
                TaxonomyLinkCandidate.extracted_term_id.in_(unlinked_terms),
            ).distinct()
        )) if unlinked_terms else set()
        pending = sum(1 for s in skills if s.id not in linked and s.extracted_term_id in pending_terms)
        return {"approved_skills": len(skills), "approved_link": len(linked),
                "pending_link": pending, "no_link": len(skills) - len(linked) - pending}
