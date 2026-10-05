"""API schemas for reviews and audit logs."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    payload: dict
    status: str
    reviewer_id: uuid.UUID | None = None
    decision_note: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewDecision(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class AuditLogRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    outcome: str
    request_method: str | None = None
    request_path: str | None = None
    metadata_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}
