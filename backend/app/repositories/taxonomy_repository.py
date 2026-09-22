from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    ApprovedTaxonomyLink,
    EscoOnetMapping,
    ExtractedCandidateTerm,
    ExtractedJobTerm,
    Occupation,
    TaxonomyConcept,
    TaxonomyLabel,
    TaxonomyLinkCandidate,
    TaxonomySource,
    TaxonomyVersion,
)


class TaxonomyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create_source(
        self, code: str, name: str, homepage_url: str, description: str
    ) -> TaxonomySource:
        source = self.db.scalar(select(TaxonomySource).where(TaxonomySource.code == code))
        if source:
            return source
        source = TaxonomySource(
            code=code, name=name, homepage_url=homepage_url, description=description
        )
        self.db.add(source)
        self.db.flush()
        return source

    def replace_version(
        self,
        source: TaxonomySource,
        version: str,
        release_date: str,
        import_filename: str,
        checksum: str,
        is_sample: bool,
    ) -> TaxonomyVersion:
        existing = self.db.scalar(
            select(TaxonomyVersion).where(
                TaxonomyVersion.source_id == source.id,
                TaxonomyVersion.version == version,
            )
        )
        if existing:
            self.db.delete(existing)
            self.db.flush()
        self.db.query(TaxonomyVersion).filter(TaxonomyVersion.source_id == source.id).update(
            {TaxonomyVersion.status: "inactive"}, synchronize_session=False
        )
        taxonomy_version = TaxonomyVersion(
            source_id=source.id,
            version=version,
            release_date=release_date,
            import_filename=import_filename,
            checksum=checksum,
            status="active",
            is_sample=is_sample,
            imported_at=datetime.now(timezone.utc),
        )
        self.db.add(taxonomy_version)
        self.db.flush()
        return taxonomy_version

    def add_concept(
        self,
        taxonomy_version_id: UUID,
        external_id: str,
        preferred_label: str,
        normalized_label: str,
        description: str,
        concept_type: str,
        language: str,
        alternative_labels: list[tuple[str, str]],
        metadata_json: dict,
    ) -> TaxonomyConcept:
        concept = TaxonomyConcept(
            taxonomy_version_id=taxonomy_version_id,
            external_id=external_id,
            preferred_label=preferred_label,
            normalized_label=normalized_label,
            description=description,
            concept_type=concept_type,
            language=language,
            metadata_json=metadata_json,
        )
        self.db.add(concept)
        self.db.flush()
        for label, normalized in alternative_labels:
            if normalized and normalized != normalized_label:
                concept.labels.append(
                    TaxonomyLabel(
                        label=label,
                        normalized_label=normalized,
                        label_type="alternative",
                        language=language,
                    )
                )
        return concept

    def add_occupation(
        self,
        taxonomy_version_id: UUID,
        concept_id: UUID | None,
        code: str,
        title: str,
        description: str,
        job_zone: int | None,
        metadata_json: dict,
    ) -> Occupation:
        occupation = Occupation(
            taxonomy_version_id=taxonomy_version_id,
            concept_id=concept_id,
            code=code,
            title=title,
            description=description,
            job_zone=job_zone,
            metadata_json=metadata_json,
        )
        self.db.add(occupation)
        self.db.flush()
        return occupation

    def active_concepts(self) -> list[TaxonomyConcept]:
        return list(
            self.db.scalars(
                select(TaxonomyConcept)
                .join(TaxonomyVersion)
                .options(
                    selectinload(TaxonomyConcept.labels),
                    selectinload(TaxonomyConcept.taxonomy_version).selectinload(TaxonomyVersion.source),
                )
                .where(TaxonomyVersion.status == "active")
            ).unique()
        )

    def search_concepts(
        self, query: str, source_code: str | None, concept_type: str | None, limit: int
    ) -> list[TaxonomyConcept]:
        pattern = f"%{query}%"
        statement = (
            select(TaxonomyConcept)
            .join(TaxonomyVersion)
            .join(TaxonomySource)
            .outerjoin(TaxonomyLabel)
            .options(
                selectinload(TaxonomyConcept.labels),
                selectinload(TaxonomyConcept.taxonomy_version).selectinload(TaxonomyVersion.source),
            )
            .where(
                TaxonomyVersion.status == "active",
                or_(
                    TaxonomyConcept.normalized_label.ilike(pattern),
                    TaxonomyConcept.preferred_label.ilike(pattern),
                    TaxonomyLabel.normalized_label.ilike(pattern),
                ),
            )
        )
        if source_code:
            statement = statement.where(TaxonomySource.code == source_code.upper())
        if concept_type:
            statement = statement.where(TaxonomyConcept.concept_type == concept_type)
        return list(self.db.scalars(statement.limit(limit)).unique())

    def get_concept(self, concept_id: UUID) -> TaxonomyConcept | None:
        return self.db.scalar(
            select(TaxonomyConcept)
            .options(
                selectinload(TaxonomyConcept.labels),
                selectinload(TaxonomyConcept.taxonomy_version).selectinload(TaxonomyVersion.source),
            )
            .where(TaxonomyConcept.id == concept_id)
        )

    def get_occupation(self, occupation_id: UUID) -> Occupation | None:
        return self.db.scalar(
            select(Occupation)
            .options(selectinload(Occupation.taxonomy_version).selectinload(TaxonomyVersion.source))
            .where(Occupation.id == occupation_id)
        )

    def list_versions(self) -> list[TaxonomyVersion]:
        return list(
            self.db.scalars(
                select(TaxonomyVersion)
                .options(selectinload(TaxonomyVersion.source))
                .order_by(TaxonomyVersion.imported_at.desc())
            )
        )

    def candidate_terms_for_document(self, document_id: UUID) -> list[ExtractedCandidateTerm]:
        return list(
            self.db.scalars(
                select(ExtractedCandidateTerm).where(
                    ExtractedCandidateTerm.cv_document_id == document_id,
                    ExtractedCandidateTerm.review_status != "rejected",
                )
            )
        )

    def job_terms_for_document(self, document_id: UUID) -> list[ExtractedJobTerm]:
        return list(
            self.db.scalars(
                select(ExtractedJobTerm).where(
                    ExtractedJobTerm.job_id == document_id,
                    ExtractedJobTerm.review_status != "rejected",
                )
            )
        )

    def replace_link_candidates(self, term_source: str, extracted_term_id: UUID) -> None:
        self.db.execute(
            delete(ApprovedTaxonomyLink).where(
                ApprovedTaxonomyLink.term_source == term_source,
                ApprovedTaxonomyLink.extracted_term_id == extracted_term_id,
            )
        )
        self.db.execute(
            delete(TaxonomyLinkCandidate).where(
                TaxonomyLinkCandidate.term_source == term_source,
                TaxonomyLinkCandidate.extracted_term_id == extracted_term_id,
            )
        )
        self.db.flush()

    def add_link_candidate(
        self,
        term_source: str,
        extracted_term_id: UUID,
        raw_text: str,
        normalized_text: str,
        concept_id: UUID,
        match_method: str,
        confidence_score: float,
        rank: int,
        review_status: str,
    ) -> TaxonomyLinkCandidate:
        candidate = TaxonomyLinkCandidate(
            term_source=term_source,
            extracted_term_id=extracted_term_id,
            raw_text=raw_text,
            normalized_text=normalized_text,
            concept_id=concept_id,
            match_method=match_method,
            confidence_score=confidence_score,
            rank=rank,
            review_status=review_status,
        )
        self.db.add(candidate)
        self.db.flush()
        return candidate

    def approve_candidate(
        self,
        candidate: TaxonomyLinkCandidate,
        approval_source: str,
        approved_by: UUID | None,
    ) -> ApprovedTaxonomyLink:
        now = datetime.now(timezone.utc)
        existing = self.db.scalar(
            select(ApprovedTaxonomyLink).where(
                ApprovedTaxonomyLink.term_source == candidate.term_source,
                ApprovedTaxonomyLink.extracted_term_id == candidate.extracted_term_id,
            )
        )
        if existing is None:
            existing = ApprovedTaxonomyLink(
                term_source=candidate.term_source,
                extracted_term_id=candidate.extracted_term_id,
            )
            self.db.add(existing)
        existing.concept_id = candidate.concept_id
        existing.link_candidate_id = candidate.id
        existing.match_method = candidate.match_method
        existing.confidence_score = candidate.confidence_score
        existing.approval_source = approval_source
        existing.approved_by = approved_by
        existing.approved_at = now
        candidate.review_status = "approved"
        candidate.reviewed_by = approved_by
        candidate.reviewed_at = now
        self.db.flush()
        return existing

    def get_link_candidate(self, candidate_id: UUID) -> TaxonomyLinkCandidate | None:
        return self.db.scalar(
            select(TaxonomyLinkCandidate)
            .options(
                selectinload(TaxonomyLinkCandidate.concept)
                .selectinload(TaxonomyConcept.taxonomy_version)
                .selectinload(TaxonomyVersion.source),
                selectinload(TaxonomyLinkCandidate.concept).selectinload(TaxonomyConcept.labels),
            )
            .where(TaxonomyLinkCandidate.id == candidate_id)
        )

    def pending_link_candidates(self, limit: int = 200) -> list[TaxonomyLinkCandidate]:
        return list(
            self.db.scalars(
                select(TaxonomyLinkCandidate)
                .options(
                    selectinload(TaxonomyLinkCandidate.concept)
                    .selectinload(TaxonomyConcept.taxonomy_version)
                    .selectinload(TaxonomyVersion.source),
                    selectinload(TaxonomyLinkCandidate.concept).selectinload(TaxonomyConcept.labels),
                )
                .where(TaxonomyLinkCandidate.review_status == "pending")
                .order_by(
                    TaxonomyLinkCandidate.confidence_score.desc(),
                    TaxonomyLinkCandidate.created_at.desc(),
                )
                .limit(limit)
            ).unique()
        )

    def reject_candidate(self, candidate: TaxonomyLinkCandidate, reviewed_by: UUID) -> None:
        candidate.review_status = "rejected"
        candidate.reviewed_by = reviewed_by
        candidate.reviewed_at = datetime.now(timezone.utc)
        self.db.flush()

    def find_concept_by_external_id(self, external_id: str) -> TaxonomyConcept | None:
        return self.db.scalar(
            select(TaxonomyConcept).where(TaxonomyConcept.external_id == external_id)
        )

    def find_occupation_by_code(self, code: str) -> Occupation | None:
        return self.db.scalar(select(Occupation).where(Occupation.code == code))

    def add_mapping(
        self,
        esco_concept_id: UUID,
        onet_occupation_id: UUID,
        mapping_type: str,
        confidence_score: float,
        source: str,
        version: str,
    ) -> EscoOnetMapping:
        mapping = self.db.scalar(
            select(EscoOnetMapping).where(
                EscoOnetMapping.esco_concept_id == esco_concept_id,
                EscoOnetMapping.onet_occupation_id == onet_occupation_id,
            )
        )
        if mapping is None:
            mapping = EscoOnetMapping(
                esco_concept_id=esco_concept_id,
                onet_occupation_id=onet_occupation_id,
            )
            self.db.add(mapping)
        mapping.mapping_type = mapping_type
        mapping.confidence_score = confidence_score
        mapping.source = source
        mapping.version = version
        self.db.flush()
        return mapping

    def list_mappings(self) -> list[EscoOnetMapping]:
        return list(
            self.db.scalars(
                select(EscoOnetMapping)
                .options(
                    selectinload(EscoOnetMapping.esco_concept),
                    selectinload(EscoOnetMapping.onet_occupation),
                )
                .order_by(EscoOnetMapping.created_at.desc())
            )
        )
