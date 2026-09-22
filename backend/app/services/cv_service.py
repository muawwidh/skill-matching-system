from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.models import CvDocument, User
from app.repositories.document_repository import DocumentRepository
from app.schemas.documents import CvPasteRequest
from app.services.document_parser_service import DocumentParserService
from app.nlp.skill_extractor import SkillExtractor
from app.services.section_detection_service import SectionDetectionService
from app.services.text_cleaning_service import TextCleaningService
from app.services.taxonomy_service import TaxonomyService


class CvService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DocumentRepository(db)
        self.parser = DocumentParserService()
        self.cleaner = TextCleaningService()
        self.section_detector = SectionDetectionService()
        self.skill_extractor = SkillExtractor()

    async def upload_cv(self, user: User, file: UploadFile, consent_to_process: bool) -> CvDocument:
        if not consent_to_process:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit consent is required before processing a CV.",
            )

        content = await file.read()
        parsed = self.parser.parse_upload(
            filename=file.filename or "uploaded-cv",
            content_type=file.content_type or "",
            content=content,
        )
        return self._create_and_process_cv(
            user=user,
            original_filename=file.filename or "uploaded-cv",
            content_type=parsed.content_type,
            source="upload",
            raw_text=parsed.text,
            size_bytes=len(content),
        )

    def paste_cv(self, user: User, payload: CvPasteRequest) -> CvDocument:
        if not payload.consent_to_process:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit consent is required before processing a CV.",
            )

        parsed = self.parser.parse_text(payload.text)
        return self._create_and_process_cv(
            user=user,
            original_filename=payload.original_filename,
            content_type=parsed.content_type,
            source="paste",
            raw_text=parsed.text,
            size_bytes=len(parsed.text.encode("utf-8")),
        )

    def list_my_cvs(self, user: User) -> list[CvDocument]:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        self.db.commit()
        return self.repository.list_cv_documents(profile.id)

    def get_my_cv(self, user: User, document_id: UUID) -> CvDocument:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        document = self.repository.get_cv_document(document_id, profile.id)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")
        return document

    def delete_my_cv(self, user: User, document_id: UUID) -> None:
        document = self.get_my_cv(user, document_id)
        self.repository.delete_cv_document(document)
        self.repository.add_processing_log("cv_document", document_id, "deletion", "success", "CV deleted.")
        self.db.commit()

    def process_cv(self, user: User, document_id: UUID) -> CvDocument:
        document = self.get_my_cv(user, document_id)
        cleaned_text = self.cleaner.clean(document.raw_text)
        document.cleaned_text = cleaned_text
        self._process_existing_cv(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def _create_and_process_cv(
        self,
        user: User,
        original_filename: str,
        content_type: str,
        source: str,
        raw_text: str,
        size_bytes: int,
    ) -> CvDocument:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        profile.consent_to_process_cv = True
        cleaned_text = self.cleaner.clean(raw_text)
        document = self.repository.create_cv_document(
            candidate_profile_id=profile.id,
            original_filename=original_filename,
            content_type=content_type,
            source=source,
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            size_bytes=size_bytes,
        )
        self._process_existing_cv(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def _process_existing_cv(self, document: CvDocument) -> None:
        sections = self.section_detector.detect(document.cleaned_text)
        self.repository.replace_cv_sections(document, sections)
        terms = self.skill_extractor.extract_from_sections(
            sections=sections,
            full_text=document.cleaned_text,
            document_kind="candidate",
        )
        self.repository.replace_candidate_terms(document, terms)
        TaxonomyService(self.db).link_document_if_taxonomy_available("candidate", document.id)
        document.status = "processed"
        document.error_message = ""
        document.processed_at = datetime.now(timezone.utc)
        self.repository.add_processing_log(
            "cv_document",
            document.id,
            "document_processing",
            "success",
            f"Detected {len(sections)} CV sections and {len(terms)} extracted terms.",
            {"section_count": len(sections), "term_count": len(terms)},
        )
