import uuid

from pydantic import BaseModel


class VideoCreate(BaseModel):
    source_url: str


class VideoOut(BaseModel):
    id: uuid.UUID
    source_url: str
    title: str | None
    duration: float | None
    status: str
    error: str | None

    model_config = {"from_attributes": True}


class ClipCandidateOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    start: float
    end: float
    score: float | None
    title_suggestion: str | None
    reason: str | None
    status: str

    model_config = {"from_attributes": True}


class ClipCandidateUpdate(BaseModel):
    start: float | None = None
    end: float | None = None
    title_suggestion: str | None = None


class ClipCandidateDecision(BaseModel):
    status: str  # "approved" | "rejected"


class JobOut(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    error: str | None
    video_id: uuid.UUID | None
    clip_id: uuid.UUID | None

    model_config = {"from_attributes": True}
