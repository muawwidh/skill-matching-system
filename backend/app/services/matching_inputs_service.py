from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import CandidateSkill, CvDocument, JobSkill, TaxonomyConcept
from app.db.models.explainable import (CandidateMatchingFact, JobMatchingFact, JobRequirementGroup,
    JobRequirementGroupMember, JobOccurrenceReview, JobInventoryReview)
from app.matching.policy import CLASSIFICATIONS, REVIEWS, fingerprint
from app.repositories.matching_inputs_repository import MatchingInputsRepository, snapshot


class MatchingInputsService:
    def __init__(self, db):
        self.db = db
        self.repo = MatchingInputsRepository(db)

    def profile(self, user, lock=False):
        value = self.repo.profile(user.id, lock=lock)
        if not value:
            raise HTTPException(404, "Candidate profile not found")
        return value

    def job(self, job_id, lock=False):
        value = self.repo.job(job_id, lock=lock)
        if not value:
            raise HTTPException(404, "Job not found")
        return value

    @staticmethod
    def check(expected, current):
        if expected != current:
            raise HTTPException(409, "Reviewed-input fingerprint changed; reload before writing")

    @staticmethod
    def review(user, status):
        return {"review_status": status, "reviewed_by": user.id,
                "reviewer_pseudonym_snapshot": "reviewer_" + fingerprint(str(user.id))[:16],
                "reviewer_role_snapshot": ",".join(sorted(x.name for x in user.roles)),
                "reviewed_at": datetime.now(timezone.utc), "evidence_snapshot": {}}

    def read_candidate(self, user):
        return self.repo.candidate_state(self.profile(user))

    def read_job(self, job_id):
        return self.repo.job_state(self.job(job_id))

    def mutate(self, action):
        try:
            result = action()
            self.repo.finish()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(409, "Reviewed-input constraint conflict") from exc
        except Exception:
            self.db.rollback()
            raise

    def create_fact(self, user, payload, job_id=None):
        def action():
            owner = self.job(job_id, True) if job_id else self.profile(user, True)
            if not job_id and owner.status != "active":
                raise HTTPException(409, "Inactive candidate profiles cannot create matching facts")
            state = self.repo.job_state(owner) if job_id else self.repo.candidate_state(owner)
            self.check(payload.expected_fingerprint, state["fingerprint"])
            values = payload.model_dump(exclude={"expected_fingerprint", "cv_document_id", "review_status"})
            if job_id and payload.cv_document_id:
                raise HTTPException(422, "Job facts cannot reference a CV")
            if not job_id and payload.cv_document_id:
                cv = self.db.get(CvDocument, payload.cv_document_id)
                if not cv or cv.candidate_profile_id != owner.id:
                    raise HTTPException(404, "CV not found")
            if payload.taxonomy_concept_id:
                concept = self.db.get(TaxonomyConcept, payload.taxonomy_concept_id)
                if not concept or concept.taxonomy_version_id != payload.taxonomy_release_id:
                    raise HTTPException(422, "Concept must belong to the supplied taxonomy release")
                if concept.concept_type != "occupation":
                    raise HTTPException(422, "Occupation facts require an occupation concept")
            model = JobMatchingFact if job_id else CandidateMatchingFact
            values.update(job_id=job_id) if job_id else values.update(
                candidate_profile_id=owner.id, cv_document_id=payload.cv_document_id, provenance="candidate_confirmed")
            item = model(id=uuid4(), **values, source_fingerprint=state.get("source_fingerprint", state["fingerprint"]),
                         **self.review(user, payload.review_status))
            self.db.add(item)
            self.db.flush()
            self.repo.invalidate_job(job_id) if job_id else self.repo.invalidate_candidate(owner.id)
            return snapshot(item)
        return self.mutate(action)

    def delete_fact(self, user, fact_id, expected, job_id=None):
        def action():
            owner = self.job(job_id, True) if job_id else self.profile(user, True)
            state = self.repo.job_state(owner) if job_id else self.repo.candidate_state(owner)
            self.check(expected, state["fingerprint"])
            item = self.db.get(JobMatchingFact if job_id else CandidateMatchingFact, fact_id)
            if not item or (item.job_id if job_id else item.candidate_profile_id) != owner.id:
                raise HTTPException(404, "Fact not found")
            if job_id and self.db.scalar(select(JobRequirementGroupMember.id).where(
                JobRequirementGroupMember.job_matching_fact_id == fact_id)):
                raise HTTPException(409, "Remove the referencing group before removing a fact")
            self.db.delete(item)
            self.repo.invalidate_job(job_id) if job_id else self.repo.invalidate_candidate(owner.id)
            return {"deleted": str(fact_id)}
        return self.mutate(action)

    def create_group(self, user, job_id, payload):
        def action():
            job = self.job(job_id, True)
            state = self.repo.job_state(job)
            self.check(payload.expected_fingerprint, state["fingerprint"])
            for member in payload.members:
                item = self.db.get(JobSkill if member.job_skill_id else JobMatchingFact,
                                   member.job_skill_id or member.job_matching_fact_id)
                if not item or item.job_id != job_id:
                    raise HTTPException(404, "Atomic group member not found")
                if item.review_status != "approved":
                    raise HTTPException(409, "Group members must be approved")
                kind = item.skill_type if member.job_skill_id else item.fact_type
                if payload.component == "Q":
                    if kind not in {"qualification", "experience"}:
                        raise HTTPException(422, "Q requires qualification/experience evidence")
                elif kind not in {"skill", "tool", "domain_knowledge", "language"}:
                    raise HTTPException(422, "R/P requires compatible occupational capability evidence")
            item = JobRequirementGroup(id=uuid4(), job_id=job_id,
                **payload.model_dump(exclude={"expected_fingerprint", "members", "review_status"}),
                source_fingerprint=state["source_fingerprint"], **self.review(user, payload.review_status))
            self.db.add(item)
            self.db.flush()
            self.db.add_all(JobRequirementGroupMember(id=uuid4(), job_id=job_id, group_id=item.id, **member.model_dump()) for member in payload.members)
            self.repo.invalidate_job(job_id)
            return snapshot(item)
        return self.mutate(action)

    def delete_group(self, user, job_id, group_id, expected):
        def action():
            state = self.repo.job_state(self.job(job_id, True))
            self.check(expected, state["fingerprint"])
            item = self.db.get(JobRequirementGroup, group_id)
            if not item or item.job_id != job_id:
                raise HTTPException(404, "Group not found")
            # Explicit deletes also work with SQLite's ordinary unit-test setup.
            for member in self.repo.rows(JobRequirementGroupMember, group_id=group_id):
                self.db.delete(member)
            self.db.delete(item)
            self.repo.invalidate_job(job_id)
            return {"deleted": str(group_id)}
        return self.mutate(action)

    def classify(self, user, job_id, skill_id, payload):
        def action():
            state = self.repo.job_state(self.job(job_id, True))
            self.check(payload.expected_fingerprint, state["fingerprint"])
            skill = self.db.get(JobSkill, skill_id)
            if not skill or skill.job_id != job_id:
                raise HTTPException(404, "Skill not found")
            old = self.db.scalar(select(JobOccurrenceReview).where(JobOccurrenceReview.job_skill_id == skill_id))
            values = payload.model_dump(exclude={"expected_fingerprint"})
            if old and all(getattr(old, key) == value for key, value in values.items()) and old.source_fingerprint == state["source_fingerprint"]:
                return snapshot(old)
            # Replace the review record; its per-review immutable attribution is never rewritten.
            if old:
                self.db.delete(old)
                self.db.flush()
            item = JobOccurrenceReview(id=uuid4(), job_id=job_id, job_skill_id=skill_id,
                classification=payload.classification, reason=payload.reason, source_fingerprint=state["source_fingerprint"],
                **self.review(user, payload.review_status))
            self.db.add(item)
            self.db.flush()
            self.repo.invalidate_job(job_id)
            return snapshot(item)
        return self.mutate(action)

    def signoff(self, user, job_id, payload):
        def action():
            state = self.repo.job_state(self.job(job_id, True))
            self.check(payload.expected_fingerprint, state["fingerprint"])
            if payload.inventory_complete:
                self.validate_inventory(state, payload)
            old = self.db.scalar(select(JobInventoryReview).where(JobInventoryReview.job_id == job_id))
            values = payload.model_dump(exclude={"expected_fingerprint"})
            if old and old.source_fingerprint == state["fingerprint"] and all(getattr(old, k) == v for k, v in values.items()):
                return snapshot(old)
            if old:
                self.db.delete(old)
                self.db.flush()
            item = JobInventoryReview(id=uuid4(), job_id=job_id,
                **{k: v for k, v in values.items() if k != "review_status"},
                source_fingerprint=state["fingerprint"], **self.review(user, payload.review_status))
            self.db.add(item)
            self.db.flush()
            self.repo.invalidate_job(job_id)
            return snapshot(item)
        return self.mutate(action)

    @staticmethod
    def validate_inventory(state, payload):
        groups = {str(x["id"]): x for x in state["groups"]}
        skill_members = {str(x["job_skill_id"]): groups[str(x["group_id"])] for x in state["members"] if x["job_skill_id"]}
        fact_members = {str(x["job_matching_fact_id"]): groups[str(x["group_id"])] for x in state["members"] if x["job_matching_fact_id"]}
        reviews = {str(x["job_skill_id"]): x for x in state["occurrences"]}
        for skill in state["skills"]:
            if skill["review_status"] not in REVIEWS or skill["requirement_type"] not in CLASSIFICATIONS:
                raise HTTPException(409, "Noncanonical stored occurrence")
            if skill["review_status"] == "pending":
                raise HTTPException(409, "Pending bound occurrence")
            if skill["review_status"] == "rejected":
                continue
            group = skill_members.get(str(skill["id"]))
            review = reviews.get(str(skill["id"]))
            if review:
                if review["review_status"] != "approved" or review["source_fingerprint"] != state["source_fingerprint"]:
                    raise HTTPException(409, "Unreviewed or stale occurrence classification")
                classification = review["classification"]
            else:
                classification = skill["requirement_type"]
            if classification == "unknown":
                raise HTTPException(409, "Unknown approved classification")
            if classification == "non_requirement":
                if not review or group:
                    raise HTTPException(409, "non_requirement needs explicit review and no scoring group")
                continue
            if not group or group["classification"] != classification:
                raise HTTPException(409, "Approved occurrence missing consistent scoring group")
            if skill["skill_type"] in {"qualification", "experience"} and group["component"] != "Q":
                raise HTTPException(409, "Qualification/experience must enter Q")
        for group in groups.values():
            if group["review_status"] != "approved" or group["source_fingerprint"] != state["source_fingerprint"]:
                raise HTTPException(409, "Unreviewed or stale group")
        if any(x["critical"] for x in groups.values()) and not any(x["component"] == "R" for x in groups.values()):
            raise HTTPException(409, "Critical inputs require an applicable required-skill group R")
        for fact in state["facts"]:
            if fact["review_status"] == "pending":
                raise HTTPException(409, "Pending job fact")
            if fact["review_status"] == "approved" and fact["source_fingerprint"] != state["source_fingerprint"]:
                raise HTTPException(409, "Stale job fact")
            if fact["review_status"] == "approved" and fact["fact_type"] in {"qualification", "experience"} and str(fact["id"]) not in fact_members:
                raise HTTPException(409, "Q fact missing scoring group")
        if payload.o_applicability == "not_applicable" and any(x["review_status"] == "approved" and x["fact_type"] == "occupation" for x in state["facts"]):
            raise HTTPException(409, "Occupation scope contradicts not_applicable")
        if payload.q_applicability == "not_applicable" and any(x["component"] == "Q" for x in groups.values()):
            raise HTTPException(409, "Q scope contradicts not_applicable")
