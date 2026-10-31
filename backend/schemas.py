from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class CriminalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None
    nickname: str
    reward: Decimal
    latitude: float | None
    longitude: float | None
    location_note: str | None
    difficulty: int
    armed: bool
    has_crew: bool
    escape_master: bool


class HuntCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    criminal_id: int = Field(gt=0, strict=True)
    success: StrictBool
    notes: str = Field(min_length=1, max_length=5000)


class HuntPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    success: StrictBool | None = None
    notes: str | None = Field(default=None, min_length=1, max_length=5000)

    @model_validator(mode="after")
    def require_non_null_change(self):
        if not self.model_fields_set:
            raise ValueError("Provide success or notes")
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("success and notes cannot be null")
        return self


class HuntRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    criminal_id: int
    success: bool
    notes: str
    created_at: datetime
