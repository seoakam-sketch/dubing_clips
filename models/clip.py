import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.db import Base
from models.enums import ClipStatus


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clip_candidates.id", ondelete="CASCADE"), nullable=False
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    cropped_path: Mapped[str | None] = mapped_column(String, nullable=True)
    dubbed_path: Mapped[str | None] = mapped_column(String, nullable=True)
    subtitle_path: Mapped[str | None] = mapped_column(String, nullable=True)
    final_output_path: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default=ClipStatus.queued.value, nullable=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    clip_candidate: Mapped["ClipCandidate"] = relationship(back_populates="clip")
