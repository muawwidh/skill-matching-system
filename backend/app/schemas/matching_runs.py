"""An explicit request, never a client-supplied score, pool or policy override."""
from pydantic import BaseModel, ConfigDict


class CreateMatchingRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
