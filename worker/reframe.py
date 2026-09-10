import json
import subprocess

from models.clip import Clip
from models.db import SessionLocal
from models.enums import ClipStatus
from worker.celery_app import app
from worker.config import clip_dir
from worker.job_utils import job_run

TARGET_W, TARGET_H = 1080, 1920


def _probe_dimensions(path: str) -> tuple[int, int]:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", path,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    stream = json.loads(out)["streams"][0]
    return stream["width"], stream["height"]


def _center_crop_filter(src_w: int, src_h: int) -> str:
    target_ratio = TARGET_W / TARGET_H
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        crop_w = int(src_h * target_ratio)
        crop_h = src_h
    else:
        crop_w = src_w
        crop_h = int(src_w / target_ratio)
    return f"crop={crop_w}:{crop_h}:(iw-{crop_w})/2:(ih-{crop_h})/2,scale={TARGET_W}:{TARGET_H}"


def _face_center_x(path: str, src_w: int, src_h: int) -> float | None:
    """Samples a few frames with mediapipe face detection and returns the
    average detected face center as a fraction of width (0-1), or None if no
    face was found — callers should fall back to a plain center crop.
    """
    try:
        import cv2
        import mediapipe as mp
    except ImportError:
        return None

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    sample_indices = {int(frame_count * f) for f in (0.1, 0.3, 0.5, 0.7, 0.9)}

    centers = []
    with mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5) as detector:
        idx = 0
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            if idx in sample_indices:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = detector.process(rgb)
                if result.detections:
                    box = result.detections[0].location_data.relative_bounding_box
                    centers.append(box.xmin + box.width / 2)
            idx += 1
    cap.release()

    if not centers:
        return None
    return sum(centers) / len(centers)


def _dynamic_crop_filter(src_w: int, src_h: int, face_center_x: float) -> str:
    target_ratio = TARGET_W / TARGET_H
    if src_w / src_h > target_ratio:
        crop_w = int(src_h * target_ratio)
        crop_h = src_h
    else:
        crop_w = src_w
        crop_h = int(src_w / target_ratio)

    center_px = face_center_x * src_w
    x = int(min(max(center_px - crop_w / 2, 0), src_w - crop_w))
    return f"crop={crop_w}:{crop_h}:{x}:(ih-{crop_h})/2,scale={TARGET_W}:{TARGET_H}"


@app.task(name="worker.reframe.reframe_vertical", bind=True, max_retries=1)
def reframe_vertical(self, clip_id: str) -> str:
    session = SessionLocal()
    try:
        clip = session.get(Clip, clip_id)
        if clip is None:
            raise ValueError(f"clip {clip_id} not found")

        try:
            with job_run("reframe", video_id=str(clip.video_id), clip_id=clip_id):
                src_w, src_h = _probe_dimensions(clip.cropped_path)
                face_center_x = _face_center_x(clip.cropped_path, src_w, src_h)

                if face_center_x is not None:
                    vf = _dynamic_crop_filter(src_w, src_h, face_center_x)
                else:
                    vf = _center_crop_filter(src_w, src_h)

                out_path = str(clip_dir(clip_id) / "reframed.mp4")
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", clip.cropped_path,
                        "-vf", vf, "-c:a", "copy", out_path,
                    ],
                    check=True,
                    capture_output=True,
                )
                clip.cropped_path = out_path
                clip.status = ClipStatus.reframing.value
                session.commit()
        except Exception as exc:  # noqa: BLE001
            clip.status = ClipStatus.failed.value
            clip.error = str(exc)
            session.commit()
            raise

        return clip_id
    finally:
        session.close()
