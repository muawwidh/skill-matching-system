"""Languages on the candidate's profile.

A profile language is a "language" skill that was found by the language rule in
a CV or added on My profile. Profile languages are compared with a job's
language requirements by name only and are kept out of the matching profile
(embedding) and of the skill coverage, so they never affect the ranking.
Skills a candidate typed as "language" in the skill editor before this
existed keep their former behaviour (they stay in the matching profile); they
still count as the candidate's languages in the comparison.
"""
from collections.abc import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CandidateSkill, ExtractedCandidateTerm, User
from app.repositories.document_repository import DocumentRepository

LANGUAGE_TYPE = "language"
LANGUAGE_SOURCE = "manual_language"  # languages the candidate added on My profile
LANGUAGE_RULE_PREFIX = "language_rule@"
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2", "native")


def profile_language_ids(db: Session, skills: Iterable[CandidateSkill]) -> set[UUID]:
    """IDs of the given skills that are profile languages (added on My profile or found by the language rule)."""
    languages = [skill for skill in skills if skill.skill_type == LANGUAGE_TYPE]
    ids = {skill.id for skill in languages if skill.source == LANGUAGE_SOURCE}
    term_ids = {skill.extracted_term_id: skill.id for skill in languages if skill.extracted_term_id}
    if term_ids:
        for term_id, method in db.execute(select(ExtractedCandidateTerm.id, ExtractedCandidateTerm.extraction_method)
                                          .where(ExtractedCandidateTerm.id.in_(list(term_ids)))):
            if method.startswith(LANGUAGE_RULE_PREFIX):
                ids.add(term_ids[term_id])
    return ids


def display_language(name: str) -> str:
    return " ".join(word[:1].upper() + word[1:] for word in name.split())


class LanguageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DocumentRepository(db)

    def _skills(self, user: User) -> list[CandidateSkill]:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        return [skill for skill in self.repository.list_candidate_skills(profile.id)
                if skill.skill_type == LANGUAGE_TYPE]

    def list_languages(self, user: User) -> list[dict]:
        """The candidate's languages (rejected ones left out), one entry per skill row."""
        skills = [skill for skill in self._skills(user) if skill.review_status != "rejected"]
        profile_ids = profile_language_ids(self.db, skills)
        entries = []
        for skill in skills:
            origin = ("added" if skill.source == LANGUAGE_SOURCE else
                      "cv" if skill.id in profile_ids else "skill_editor")
            entries.append({"id": skill.id, "label": display_language(skill.raw_text), "name": skill.normalized_text,
                            "level": skill.proficiency_level, "status": skill.review_status, "origin": origin,
                            "evidence": skill.evidence_sentence})
        return sorted(entries, key=lambda e: (e["name"], e["origin"], str(e["id"])))

    def add_language(self, user: User, name: str, level: str | None) -> CandidateSkill:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        text = " ".join(name.split())
        normalized = text.lower()
        if any(skill.source == LANGUAGE_SOURCE and skill.normalized_text == normalized for skill in self._skills(user)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already added this language.")
        skill = CandidateSkill(candidate_profile_id=profile.id, raw_text=text, normalized_text=normalized,
                               skill_type=LANGUAGE_TYPE, evidence_sentence="", confidence_score=1.0,
                               review_status="approved", source=LANGUAGE_SOURCE, proficiency_level=level)
        self.db.add(skill)
        self.db.flush()
        self.repository.add_processing_log("candidate_profile", profile.id, "language", "success",
                                           "Added a language by hand.", {"language_count": 1})
        self.db.commit()
        return skill

    def remove_language(self, user: User, skill_id: UUID) -> None:
        """Remove a language the candidate added by hand; languages from a CV are rejected instead."""
        skill = next((s for s in self._skills(user) if s.id == skill_id and s.source == LANGUAGE_SOURCE), None)
        if skill is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Language not found.")
        profile_id = skill.candidate_profile_id
        self.db.delete(skill)
        self.repository.add_processing_log("candidate_profile", profile_id, "language", "success",
                                           "Removed a language added by hand.", {"language_count": 1})
        self.db.commit()

    def review_language(self, user: User, skill_id: UUID, decision: str) -> CandidateSkill:
        """Confirm or reject a language found in a CV. The decision is kept."""
        skills = self._skills(user)
        found = {s.id for s in skills} & profile_language_ids(self.db, skills)
        skill = next((s for s in skills if s.id == skill_id and s.id in found and s.source != LANGUAGE_SOURCE), None)
        if skill is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Language not found.")
        skill.review_status = decision
        self.repository.add_processing_log("candidate_profile", skill.candidate_profile_id, "language", "success",
                                           f"Language from a CV {decision}.", {"language_count": 1})
        self.db.commit()
        return skill
