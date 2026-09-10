import uuid

from celery import chain
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import ClipCandidateDecision, ClipCandidateOut, ClipCandidateUpdate
from models.clip_candidate import ClipCandidate
from models.enums import ClipCandidateStatus
from worker.celery_app import app as celery_app

router = APIRouter(prefix="/clip-candidates", tags=["clips"])


@router.get("", response_model=list[ClipCandidateOut])
def list_clip_candidates(video_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(ClipCandidate)
    if video_id:
        query = query.filter(ClipCandidate.video_id == video_id)
    return query.order_by(ClipCandidate.start).all()


@router.patch("/{candidate_id}", response_model=ClipCandidateOut)
def edit_clip_candidate(
    candidate_id: uuid.UUID, payload: ClipCandidateUpdate, db: Session = Depends(get_db)
):
    candidate = db.get(ClipCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="clip candidate not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(candidate, field, value)
    candidate.status = ClipCandidateStatus.edited.value
    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("/{candidate_id}/decision", response_model=ClipCandidateOut)
def decide_clip_candidate(
    candidate_id: uuid.UUID, payload: ClipCandidateDecision, db: Session = Depends(get_db)
):
    candidate = db.get(ClipCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="clip candidate not found")
    if payload.status not in (ClipCandidateStatus.approved.value, ClipCandidateStatus.rejected.value):
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'")

    candidate.status = payload.status
    db.commit()
    db.refresh(candidate)

    if payload.status == ClipCandidateStatus.approved.value:
        _enqueue_clip_pipeline(str(candidate.id))

    return candidate


def _enqueue_clip_pipeline(candidate_id: str) -> None:
    # Each stage is its own Celery task with independent error handling
    # (see worker.job_utils.job_run); a failure in, say, dubbing does not
    # abort sibling clips or the parent video's pipeline. Enqueued by task
    # name so the API container never needs the worker's ML dependencies.
    chain(
        celery_app.signature("worker.clip.cut_clip", args=(candidate_id,)),
        celery_app.signature("worker.reframe.reframe_vertical"),
        celery_app.signature("worker.separate_audio.separate_audio"),
        celery_app.signature("worker.translate.translate_segment"),
        celery_app.signature("worker.dub.synthesize_dub"),
        celery_app.signature("worker.mix_audio.mix_audio"),
        celery_app.signature("worker.subtitle.generate_subtitles"),
        celery_app.signature("worker.render.render_final"),
    ).apply_async()
