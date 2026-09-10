import uuid

from celery import chain
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import VideoCreate, VideoOut
from models.enums import VideoStatus
from models.video import Video
from worker.celery_app import app as celery_app

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("", response_model=VideoOut, status_code=201)
def create_video(payload: VideoCreate, db: Session = Depends(get_db)):
    video = Video(id=uuid.uuid4(), source_url=payload.source_url, status=VideoStatus.pending.value)
    db.add(video)
    db.commit()
    db.refresh(video)

    # Enqueue by task name (celery_app.signature) rather than importing the
    # task functions: the API container only installs requirements/api.txt,
    # not the worker's heavy ML deps (yt-dlp, faster-whisper, ...).
    chain(
        celery_app.signature("worker.download.download_video", args=(str(video.id),)),
        celery_app.signature("worker.transcribe.transcribe_video"),
        celery_app.signature("worker.highlight.detect_highlights"),
    ).apply_async()

    return video


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: uuid.UUID, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")
    return video


@router.get("", response_model=list[VideoOut])
def list_videos(db: Session = Depends(get_db)):
    return db.query(Video).order_by(Video.created_at.desc()).all()
