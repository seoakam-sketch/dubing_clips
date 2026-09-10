import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import JobOut
from models.job import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    video_id: uuid.UUID | None = None,
    clip_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if video_id:
        query = query.filter(Job.video_id == video_id)
    if clip_id:
        query = query.filter(Job.clip_id == clip_id)
    return query.order_by(Job.created_at.desc()).all()
