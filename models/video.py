import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.db import Base
from models.enums import VideoStatus


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    downloaded_path: Mapped[str | None] = mapped_column(String, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default=VideoStatus.pending.value, nullable=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    video_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    clip_candidates: Mapped[list["ClipCandidate"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
