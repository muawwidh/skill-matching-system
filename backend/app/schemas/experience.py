"""Work entries and relevant experience (D060)."""
import re
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

_MONTH = re.compile(r"^(19|20)\d{2}-(0[1-9]|1[0-2])$")


def month_to_date(value: str) -> date:
    return date(int(value[:4]), int(value[5:7]), 1)


def date_to_month(value: date | None) -> str | None:
    return value.strftime("%Y-%m") if value else None


class OccupationRead(BaseModel):
    concept_id: UUID
    label: str
    isco_code: str | None
    isco_unit_group: str = ""


class WorkEntryWrite(BaseModel):
    """`start_month`/`end_month` as YYYY-MM; `end_month` null means "present". No employer field."""
    title: str = Field(min_length=1, max_length=255)
    start_month: str
    end_month: str | None = None
    occupation_concept_id: UUID | None = None
    source: str = Field(default="manual", pattern=r"^(manual|cv_detected)$")

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("The job title is required.")
        return value

    @field_validator("start_month", "end_month")
    @classmethod
    def _month(cls, value: str | None) -> str | None:
        if value is not None and not _MONTH.match(value):
            raise ValueError("Use the format YYYY-MM.")
        return value

    @model_validator(mode="after")
    def _period(self):
        if self.end_month is not None and self.end_month < self.start_month:
            raise ValueError("The end month is before the start month.")
        return self


class WorkEntryRead(BaseModel):
    id: UUID
    title: str
    start_month: str
    end_month: str | None
    source: str
    months: int
    occupation: OccupationRead | None


class DetectedWorkEntryRead(BaseModel):
    """A dated entry found in the candidate's CV; shown to pre-fill the form, never stored by itself."""
    title: str  # "" when uncertain: ask with `title_choices`
    title_choices: list[str] = []  # "Which of these is your job title?"; never company-like parts
    start_month: str
    end_month: str | None
    month_precision: bool


class OccupationSuggestionRead(OccupationRead):
    confidence: float
    # "label": string-based linker; "embedding": nearest neighbour by meaning (shown after).
    method: str = "label"
