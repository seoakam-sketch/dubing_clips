import uuid

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.db import Base


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    start: Mapped[float] = mapped_column(Float, nullable=False)
    end: Mapped[float] = mapped_column(Float, nullable=False)
    text_original: Mapped[str] = mapped_column(Text, nullable=False)
    text_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker: Mapped[str | None] = mapped_column(String, nullable=True)
    # Word-level timestamps as produced by faster-whisper: [{"word": str, "start": float, "end": float}, ...]
    words: Mapped[list | None] = mapped_column(JSON, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="transcript_segments")
