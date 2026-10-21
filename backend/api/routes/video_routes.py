"""Video upload, analysis and status endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from backend.api.dependencies import app_settings, db_session
from backend.api.mappers import video_to_schema
from backend.core.config import Settings
from backend.core.exceptions import VisionDependencyError
from backend.core.logging_config import get_logger
from backend.models.video import Video
from backend.schemas.enums import VideoStatus
from backend.schemas.system_schema import VideoAnalyzeResponse, VideoRead

logger = get_logger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])

ALLOWED_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}
MAX_UPLOAD_BYTES = 512 * 1024 * 1024


@router.post("", response_model=VideoRead, status_code=201)
@router.post("/", response_model=VideoRead, status_code=201, include_in_schema=False)
def upload_video(
    file: UploadFile = File(...),
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> VideoRead:
    """Upload a porch video and return its identifier."""
    filename = file.filename or "upload.mp4"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format '{suffix}'. Allowed: {sorted(ALLOWED_SUFFIXES)}",
        )

    settings.ensure_directories()
    video_id = str(uuid.uuid4())
    target = settings.uploads_dir / f"{video_id}{suffix}"

    size = 0
    with target.open("wb") as handle:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                handle.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="The video is larger than 512 MB")
            handle.write(chunk)

    if size == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The uploaded file is empty")

    record = Video(
        video_id=video_id,
        filename=filename,
        path=str(target),
        status=VideoStatus.UPLOADED.value,
        created_at=datetime.now(UTC),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    logger.info("Video uploaded video_id=%s filename=%s size=%s", video_id, filename, size)
    return video_to_schema(record)


@router.get("", response_model=list[VideoRead])
def list_videos(
    session: Session = Depends(db_session),
    limit: int = 50,
) -> list[VideoRead]:
    """List the uploaded videos, newest first."""
    statement = select(Video).order_by(Video.created_at.desc()).limit(limit)  # type: ignore[union-attr]
    return [video_to_schema(record) for record in session.exec(statement).all()]


@router.post("/{video_id}/analyze", response_model=VideoAnalyzeResponse, status_code=202)
def analyze_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> VideoAnalyzeResponse:
    """Start the analysis of an uploaded video in the background."""
    record = session.get(Video, video_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
    if record.status == VideoStatus.ANALYZING.value:
        raise HTTPException(status_code=409, detail="This video is already being analyzed")
    if record.status == VideoStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="This video has already been analyzed")

    record.status = VideoStatus.ANALYZING.value
    record.error = None
    session.add(record)
    session.commit()

    background_tasks.add_task(_run_analysis, video_id)
    return VideoAnalyzeResponse(
        video_id=video_id,
        status=VideoStatus.ANALYZING,
        message="Analysis started",
    )


@router.get("/{video_id}/status", response_model=VideoRead)
def video_status(video_id: str, session: Session = Depends(db_session)) -> VideoRead:
    """Return the progress of the analysis of a video."""
    record = session.get(Video, video_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
    return video_to_schema(record)


@router.get("/{video_id}/annotated")
def annotated_video(video_id: str, session: Session = Depends(db_session)):
    """Stream the annotated video."""
    from fastapi.responses import FileResponse  # noqa: PLC0415 - local import

    record = session.get(Video, video_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
    if not record.annotated_path or not Path(record.annotated_path).is_file():
        raise HTTPException(status_code=404, detail="The annotated video is not ready yet")
    return FileResponse(record.annotated_path, media_type="video/mp4")


def _run_analysis(video_id: str) -> None:
    """Background task running the vision pipeline over an uploaded video."""
    from backend.core.db import session_scope  # noqa: PLC0415 - local import
    from backend.services.pipeline_service import ingest_event  # noqa: PLC0415 - local import
    from backend.services.video_service import analyze_video  # noqa: PLC0415 - local import

    settings = app_settings()
    with session_scope() as session:
        record = session.get(Video, video_id)
        if record is None:
            return
        path = record.path
        session_id = _active_session_id(session)

    def on_event(event) -> None:  # noqa: ANN001 - EventCreate
        """Push one vision event through the ingestion pipeline."""
        with session_scope() as event_session:
            ingest_event(event_session, event, settings, video_id=video_id)

    def on_progress(progress: float, current_time_s: float, frame_index: int) -> None:
        with session_scope() as progress_session:
            row = progress_session.get(Video, video_id)
            if row is None:
                return
            row.progress = round(progress, 4)
            row.current_time_s = round(current_time_s, 3)
            row.frames_processed = frame_index
            progress_session.add(row)

    try:
        result = analyze_video(
            path,
            session_id=session_id,
            on_event=on_event,
            settings=settings,
            progress_callback=on_progress,
        )
    except (VisionDependencyError, FileNotFoundError) as exc:
        logger.error("Analysis failed for %s: %s", video_id, exc)
        with session_scope() as session:
            row = session.get(Video, video_id)
            if row is not None:
                row.status = VideoStatus.FAILED.value
                row.error = str(exc)
                session.add(row)
        return
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected analysis failure for %s", video_id)
        with session_scope() as session:
            row = session.get(Video, video_id)
            if row is not None:
                row.status = VideoStatus.FAILED.value
                row.error = str(exc)
                session.add(row)
        return

    with session_scope() as session:
        row = session.get(Video, video_id)
        if row is not None:
            row.status = VideoStatus.COMPLETED.value
            row.progress = 1.0
            row.duration_s = result.duration_s
            row.frames_processed = result.frames_processed
            row.total_frames = result.total_frames
            row.annotated_path = result.annotated_path
            session.add(row)


def _active_session_id(session: Session) -> str | None:
    """Return the id of the active protection session, if any."""
    from backend.services.protection_service import ProtectionSessionManager  # noqa: PLC0415

    manager = ProtectionSessionManager(session)
    active = manager.get_active_session()
    return active.session_id if active else None
