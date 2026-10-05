from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.db.base import Base, TimestampMixin


class EmbeddingColumns(TimestampMixin):
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    model_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    taxonomy_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CandidateProfileEmbedding(EmbeddingColumns, Base):
    __tablename__ = "candidate_profile_embeddings"
    __table_args__ = (
        UniqueConstraint("candidate_profile_id", "model_id", "model_revision", "template_version", name="uq_profile_embedding_identity"),
        CheckConstraint("status in ('ready', 'stale', 'failed')", name="ck_profile_embedding_status"),
    )

    candidate_profile_id: Mapped[UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)


class JobEmbedding(EmbeddingColumns, Base):
    __tablename__ = "job_embeddings"
    __table_args__ = (
        UniqueConstraint("job_id", "model_id", "model_revision", "template_version", name="uq_job_embedding_identity"),
        CheckConstraint("status in ('ready', 'stale', 'failed')", name="ck_job_embedding_status"),
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
