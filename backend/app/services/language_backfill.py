"""Add languages to existing CVs, additively (dry-run unless --apply).

Runs only the CV language rule (method language_rule@v4) on each processed CV and
adds a pending "language" term and skill for every language that CV does not have
yet from that rule. Nothing else is re-extracted, existing terms, skills and review
decisions are never changed, and the CVs of the users in --exclude-mapping
("candidates": {alias: user ID}, the evaluation profiles) are never touched.
Profile languages are not part of the matching profile, so no embedding changes.

    python -m app.services.language_backfill --exclude-mapping database-mapping.json [--apply]
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CandidateProfile, CandidateSkill, CvDocument, ExtractedCandidateTerm
from app.nlp.skill_extractor import ExtractedTerm, SkillExtractor
from app.retrieval.auto_reindex import DISABLED_KEY
from app.services.language_service import LANGUAGE_RULE_PREFIX
from app.services.section_detection_service import SectionDetectionService


def excluded_users(mapping_path: Path) -> set[UUID]:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    users = {UUID(value) for value in mapping.get("candidates", {}).values()}
    if not users:
        raise ValueError(f"No candidate users in {mapping_path}")
    return users


def cv_language_terms(document: CvDocument) -> list[ExtractedTerm]:
    sections = SectionDetectionService().detect(document.cleaned_text)
    terms = SkillExtractor().extract_from_sections(sections, document.cleaned_text, "candidate")
    return [term for term in terms if term.extraction_method.startswith(LANGUAGE_RULE_PREFIX)]


def backfill(db: Session, exclude_users: set[UUID], apply: bool = False) -> Counter:
    counts: Counter = Counter()
    documents = db.scalars(select(CvDocument).join(CandidateProfile,
                                                   CvDocument.candidate_profile_id == CandidateProfile.id)
                           .where(CvDocument.status == "processed", CandidateProfile.user_id.not_in(exclude_users))
                           .order_by(CvDocument.id)).all()
    counts["excluded_cvs"] = db.query(CvDocument).join(CandidateProfile).filter(
        CandidateProfile.user_id.in_(exclude_users)).count()
    for document in documents:
        counts["cvs"] += 1
        known = {(normalized, start) for normalized, start in db.execute(
            select(ExtractedCandidateTerm.normalized_text, ExtractedCandidateTerm.start_char).where(
                ExtractedCandidateTerm.cv_document_id == document.id,
                ExtractedCandidateTerm.extraction_method.startswith(LANGUAGE_RULE_PREFIX)))}
        new = [term for term in cv_language_terms(document) if (term.normalized_text, term.start_char) not in known]
        if new:
            counts["cvs_with_new_languages"] += 1
        counts["languages_added"] += len(new)
        if not apply:
            continue
        for term in new:
            row = ExtractedCandidateTerm(
                cv_document_id=document.id, raw_text=term.raw_text, normalized_text=term.normalized_text,
                term_type=term.term_type, source_section=term.source_section,
                evidence_sentence=term.evidence_sentence, extraction_method=term.extraction_method,
                confidence_score=term.confidence_score, start_char=term.start_char, end_char=term.end_char)
            db.add(row)
            db.flush()
            db.add(CandidateSkill(candidate_profile_id=document.candidate_profile_id, extracted_term_id=row.id,
                                  raw_text=term.raw_text, normalized_text=term.normalized_text,
                                  skill_type=term.term_type, evidence_sentence=term.evidence_sentence,
                                  confidence_score=term.confidence_score, review_status="pending"))
    if apply:
        db.commit()
    return counts


def main(argv: list[str] | None = None) -> int:
    from app.db.session import SessionLocal

    parser = argparse.ArgumentParser(description="Add CV languages additively (dry-run unless --apply).")
    parser.add_argument("--exclude-mapping", type=Path, required=True,
                        help="JSON with 'candidates': {alias: user ID}; these users' CVs are never touched")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    exclude = excluded_users(args.exclude_mapping)
    with SessionLocal() as db:
        db.info[DISABLED_KEY] = True  # profile languages are not embedded
        counts = backfill(db, exclude, args.apply)
    print(("Applied" if args.apply else "Dry run") + ": " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
