from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RetrievedJob(BaseModel):
    rank: int
    job_id: UUID
    title: str
    company: str
    location: str
    employment_type: str
    retrieval_similarity: float
    model_id: str
    model_revision: str
    template_version: str
    candidate_input_hash: str
    job_input_hash: str
    candidate_indexed_at: datetime
    job_indexed_at: datetime
