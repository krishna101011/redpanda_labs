from __future__ import annotations

import asyncio
import io
import json
import logging
import platform
import shutil
import subprocess
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import APP_NAME, APP_VERSION, CACHE_DIR, CONFIG_DIR, DATA_DIR, LAB_IMAGE, PROJECT_ROOT, ensure_data_directories
from app.database import get_db, run_migrations
from app.models import Achievement, ChallengeOverride, ChallengeProgress, CompletionHistory, Note, Preference, WorkspaceRecord, utcnow
from app.services import ai
from app.services.ai import AIConfigurationError
from app.services.challenges import ChallengeManifest, get_manifest, load_builtins, registry, safe_relative_path, validate_manifest
from app.services.labs import LabManager, LabUnavailable, ResourceOwnershipError
from app.services.terminal import TerminalManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("redpanda-labs")
lab_manager = LabManager()
terminal_manager = TerminalManager()

ALLOWED_ORIGINS = {
    "http://127.0.0.1:8000", "http://localhost:8000",
    "http://127.0.0.1:5173", "http://localhost:5173",
}
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver"}


class LocalBrowserSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        host = (request.headers.get("host") or "").split(":", 1)[0].lower()
        if host and host not in ALLOWED_HOSTS:
            return JSONResponse({"detail": "This local application accepts requests only through localhost."}, status_code=400)
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
        return await call_next(request)


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=30000)
    challenge_id: str | None = Field(default=None, max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=30)


class NoteUpdate(NoteCreate):
    pass


class ConfirmBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str = Field(min_length=1, max_length=100)


class AISettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="OpenAI-compatible", max_length=100)
    base_url: str = Field(min_length=1, max_length=1000)
    model: str = Field(min_length=1, max_length=200)
    api_key: str = Field(default="", max_length=2000)
    timeout_seconds: int = Field(default=20, ge=3, le=120)


class MentorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)
    challenge_id: str | None = Field(default=None, max_length=80)
    selected_output: str | None = Field(default=None, max_length=8000)
    share_selected_output: bool = False


class ExplainBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=8000)
    challenge_id: str | None = Field(default=None, max_length=80)
    use_ai: bool = False
    share_confirmed: bool = False


class BuilderCreate(BaseModel):
    model_config = ConfigDict(extra="allow")
    manifest: dict[str, Any]


class BuilderUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str | None = Field(default=None, max_length=120)
    track: str | None = Field(default=None, max_length=80)
    difficulty: str | None = None
    summary: str | None = Field(default=None, max_length=240)
    description: str | None = Field(default=None, max_length=6000)
    learning_objectives: list[str] | None = Field(default=None, max_length=20)
    prerequisites: list[str] | None = Field(default=None, max_length=15)
    tags: list[str] | None = Field(default=None, max_length=30)
    offline_hints: list[dict[str, Any]] | None = Field(default=None, min_length=3, max_length=3)
    validation: dict[str, Any] | None = None
    workspace_seed: dict[str, str] | None = None
    completion_explanation: str | None = Field(default=None, max_length=6000)
    estimated_minutes: int | None = Field(default=None, ge=1, le=600)


class DataRestoreBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: dict[str, Any]
    mode: str = Field(pattern="^(merge|replace)$")
    confirmation: str = Field(min_length=1, max_length=100)


class DataPreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: dict[str, Any]


class WorkspaceRestoreBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    archive_base64: str = Field(min_length=1, max_length=15_000_000)
    confirmation: str = Field(min_length=1, max_length=100)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_data_directories()
    # Validate the built-in curriculum at each startup before advertising the lab catalogue.
    load_builtins()
    run_migrations()
    yield
    await terminal_manager.close_all()


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
app.add_middleware(LocalBrowserSecurityMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=sorted(ALLOWED_ORIGINS), allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "X-Confirm-Workspace"])


def _utc(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _progress_payload(progress: ChallengeProgress | None) -> dict[str, Any]:
    return {"state": progress.state if progress else "available", "started_at": _utc(progress.started_at) if progress else None,
            "completed_at": _utc(progress.completed_at) if progress else None, "hint_level": progress.hint_level if progress else 0,
            "latest_feedback": progress.latest_feedback if progress else None}


def _challenge_payload(manifest: dict[str, Any], db: Session) -> dict[str, Any]:
    progress_map = {item.challenge_id: item for item in db.query(ChallengeProgress).all()}
    current = progress_map.get(manifest["id"])
    prereq_missing = [pid for pid in manifest["prerequisites"] if not (progress_map.get(pid) and progress_map[pid].completed_at)]
    state = "completed" if current and current.completed_at else (current.state if current else "available")
    if prereq_missing:
        state = "locked"
    return {**manifest, "progress": _progress_payload(current), "state": state, "locked": bool(prereq_missing), "prerequisites_missing": prereq_missing}


def _manifest_or_404(challenge_id: str, db: Session) -> dict[str, Any]:
    manifest = get_manifest(challenge_id, db)
    if not manifest:
        raise HTTPException(status_code=404, detail="Challenge not found or disabled.")
    return manifest


def _unlocked_or_409(manifest: dict[str, Any], db: Session) -> None:
    completed = {row.challenge_id for row in db.query(ChallengeProgress).filter(ChallengeProgress.completed_at.is_not(None)).all()}
    missing = [item for item in manifest["prerequisites"] if item not in completed]
    if missing:
        raise HTTPException(status_code=409, detail={"message": "Complete the required prerequisite missions first.", "missing": missing})


def _get_or_create_progress(challenge_id: str, db: Session) -> ChallengeProgress:
    row = db.get(ChallengeProgress, challenge_id)
    if row is None:
        row = ChallengeProgress(challenge_id=challenge_id, state="available", hint_level=0)
        db.add(row)
        db.flush()
    return row


def _note_payload(note: Note) -> dict[str, Any]:
    return {"id": note.id, "kind": note.kind, "title": note.title, "content": note.content, "challenge_id": note.challenge_id,
            "tags": json.loads(note.tags_json), "created_at": _utc(note.created_at), "updated_at": _utc(note.updated_at)}


def _check_note_ref(challenge_id: str | None, db: Session) -> None:
    if challenge_id and not get_manifest(challenge_id, db):
        raise HTTPException(status_code=422, detail="The related challenge does not exist or is disabled.")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "name": APP_NAME, "version": APP_VERSION, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/diagnostics")
def diagnostics(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        database_status = "connected"
    except Exception as exc:
        database_status = f"error: {type(exc).__name__}"
    docker_status = lab_manager.diagnostics()
    disk = shutil.disk_usage(DATA_DIR)
    return {
        "app": {"name": APP_NAME, "version": APP_VERSION, "host": "127.0.0.1", "port": 8000, "python": platform.python_version()},
        "frontend": {"built": (PROJECT_ROOT / "frontend" / "dist" / "index.html").exists(), "node": _tool_version("node"), "npm": _tool_version("npm")},
        "database": {"status": database_status, "path_configured": True, "migration": "Alembic-managed"},
        "docker": docker_status,
        "workspaces": lab_manager.diagnostics_for_registered(db) if docker_status["available"] else [],
        "storage": {"free_bytes": disk.free, "total_bytes": disk.total, "data_directory_ready": DATA_DIR.exists(), "config_directory_ready": CONFIG_DIR.exists(), "cache_directory_ready": CACHE_DIR.exists()},
        "release_ready": False,
        "release_note": "This build has not passed real Docker, terminal, and network-isolation integration tests in the current environment.",
    }


def _tool_version(command: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        completed = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=2, check=False)
        return (completed.stdout or completed.stderr).strip().splitlines()[0][:100]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return "installed, version unavailable"


@app.get("/api/challenges")
def list_challenges(track: str | None = None, difficulty: str | None = None, q: str | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    manifests = registry(db)
    payload = [_challenge_payload(manifest, db) for manifest in manifests]
    if track and track != "all": payload = [item for item in payload if item["track"] == track]
    if difficulty and difficulty != "all": payload = [item for item in payload if item["difficulty"] == difficulty]
    if q:
        value = q.casefold()
        payload = [item for item in payload if value in item["title"].casefold() or value in item["summary"].casefold() or any(value in tag.casefold() for tag in item["tags"])]
    progress = [row for row in db.query(ChallengeProgress).all()]
    return {"items": payload, "total": len(payload), "overall": {"completed": sum(1 for row in progress if row.completed_at), "total": len(manifests), "in_progress": sum(1 for row in progress if row.state == "in_progress" and not row.completed_at)}}


@app.get("/api/challenges/{challenge_id}")
def get_challenge(challenge_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _challenge_payload(_manifest_or_404(challenge_id, db), db)


@app.post("/api/challenges/{challenge_id}/start")
def start_challenge(challenge_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    manifest = _manifest_or_404(challenge_id, db)
    _unlocked_or_409(manifest, db)
    try:
        workspace = lab_manager.ensure_workspace(manifest, db)
    except LabUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ResourceOwnershipError, RuntimeError, ValueError) as exc:
        logger.warning("Workspace start failed for %s: %s", challenge_id, type(exc).__name__)
        raise HTTPException(status_code=500, detail=f"The lab workspace could not be prepared safely: {exc}") from exc
    progress = _get_or_create_progress(challenge_id, db)
    if not progress.completed_at:
        progress.state = "in_progress"
        progress.started_at = progress.started_at or utcnow()
    progress.latest_feedback = "Workspace ready. The terminal is a real Bash shell inside the isolated lab container."
    db.commit()
    return {"challenge": _challenge_payload(manifest, db), "workspace": workspace, "message": "Lab workspace ready."}


@app.post("/api/challenges/{challenge_id}/validate")
def validate_challenge(challenge_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    manifest = _manifest_or_404(challenge_id, db)
    try:
        valid, feedback, evidence = lab_manager.validate(manifest, db)
    except LabUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    progress = _get_or_create_progress(challenge_id, db)
    progress.latest_feedback = feedback[0] if feedback else None
    if valid:
        if progress.completed_at is None:
            progress.completed_at = utcnow()
            progress.state = "completed"
            db.add(CompletionHistory(challenge_id=challenge_id, verification_json=json.dumps(evidence, sort_keys=True)))
            achievement_id = f"mastered-{challenge_id}"
            if db.get(Achievement, achievement_id) is None:
                db.add(Achievement(id=achievement_id, title=f"Mastered: {manifest['title']}", detail="Objective independently verified from the challenge workspace."))
            completed_count = db.query(ChallengeProgress).filter(ChallengeProgress.completed_at.is_not(None)).count() + 1
            if completed_count >= len(load_builtins()) and db.get(Achievement, "redpanda-complete") is None:
                db.add(Achievement(id="redpanda-complete", title="RedPanda Graduate", detail="Completed all 15 built-in challenges."))
        else:
            progress.state = "completed"
    db.commit()
    return {"valid": valid, "feedback": feedback, "evidence": evidence, "challenge": _challenge_payload(manifest, db), "completed_at": _utc(progress.completed_at)}


@app.post("/api/challenges/{challenge_id}/hint")
def next_hint(challenge_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    manifest = _manifest_or_404(challenge_id, db)
    progress = _get_or_create_progress(challenge_id, db)
    progress.hint_level = min(3, progress.hint_level + 1)
    db.commit()
    hint = next(item for item in manifest["offline_hints"] if item["level"] == progress.hint_level)
    return {"hint": hint, "hint_level": progress.hint_level, "complete_explanation": manifest["completion_explanation"] if progress.completed_at else None}


@app.post("/api/challenges/{challenge_id}/reset")
async def reset_workspace(challenge_id: str, body: ConfirmBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    manifest = _manifest_or_404(challenge_id, db)
    if body.confirmation != challenge_id:
        raise HTTPException(status_code=400, detail=f"Type {challenge_id} exactly to confirm this workspace reset.")
    try:
        result = lab_manager.reset_workspace(challenge_id, manifest, db)
    except LabUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ResourceOwnershipError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await terminal_manager.close(challenge_id)
    return result


@app.post("/api/challenges/{challenge_id}/restart-shell")
async def restart_shell(challenge_id: str, body: ConfirmBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _manifest_or_404(challenge_id, db)
    if body.confirmation != challenge_id:
        raise HTTPException(status_code=400, detail=f"Type {challenge_id} to restart this shell.")
    try:
        container = lab_manager.container_for(challenge_id)
        container.reload()
        if container.status != "running":
            raise LabUnavailable("The challenge container is not running. Start the lab first.")
    except (LabUnavailable, ResourceOwnershipError, Exception) as exc:
        raise HTTPException(status_code=503, detail=f"Shell restart was not performed: {str(exc)[:400]}") from exc
    await terminal_manager.close(challenge_id)
    try:
        # The shell is held by tmux inside the owned challenge container. Kill only that
        # dedicated session; reconnecting creates a fresh Bash while retaining workspace files.
        container.exec_run(["tmux", "kill-session", "-t", "redpanda-shell"], user="redpanda")
    except Exception as exc:
        logger.info("Could not explicitly close tmux session for %s: %s", challenge_id, type(exc).__name__)
    return {"restarted": True, "workspace_preserved": True, "history_preserved": True, "message": "Shell session restarted. Reconnect to create a fresh Bash in the same workspace."}


@app.post("/api/challenges/{challenge_id}/clear-progress")
def clear_challenge_progress(challenge_id: str, body: ConfirmBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _manifest_or_404(challenge_id, db)
    if body.confirmation != challenge_id:
        raise HTTPException(status_code=400, detail=f"Type {challenge_id} exactly to clear this challenge's current completion state.")
    row = db.get(ChallengeProgress, challenge_id)
    if row:
        db.delete(row)
        db.commit()
    return {"cleared": True, "preserved": ["workspace files", "notes", "saved explanations", "completion history", "historical achievements"]}


@app.get("/api/learning-path")
def learning_path(db: Session = Depends(get_db)) -> dict[str, Any]:
    items = [_challenge_payload(item, db) for item in registry(db)]
    return {"items": [{"id": x["id"], "title": x["title"], "track": x["track"], "difficulty": x["difficulty"], "state": x["state"], "prerequisites": x["prerequisites"], "prerequisites_missing": x["prerequisites_missing"]} for x in items]}


@app.get("/api/notes")
def list_notes(q: str | None = None, kind: str | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    query = db.query(Note)
    if kind in {"note", "explanation"}:
        query = query.filter(Note.kind == kind)
    notes = query.order_by(Note.updated_at.desc()).all()
    if q:
        needle = q.casefold()
        notes = [item for item in notes if needle in item.title.casefold() or needle in item.content.casefold() or needle in item.tags_json.casefold()]
    return {"items": [_note_payload(item) for item in notes], "total": len(notes)}


@app.post("/api/notes")
def create_note(body: NoteCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    _check_note_ref(body.challenge_id, db)
    item = Note(kind="note", title=body.title.strip(), content=body.content, challenge_id=body.challenge_id, tags_json=json.dumps(body.tags))
    db.add(item); db.commit(); db.refresh(item)
    return _note_payload(item)


@app.post("/api/notes/explanations")
def save_explanation(body: NoteCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    _check_note_ref(body.challenge_id, db)
    item = Note(kind="explanation", title=body.title.strip(), content=body.content, challenge_id=body.challenge_id, tags_json=json.dumps(body.tags))
    db.add(item); db.commit(); db.refresh(item)
    return _note_payload(item)


@app.put("/api/notes/{note_id}")
def update_note(note_id: str, body: NoteUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Note, note_id)
    if not item: raise HTTPException(status_code=404, detail="Notebook entry not found.")
    _check_note_ref(body.challenge_id, db)
    item.title = body.title.strip(); item.content = body.content; item.challenge_id = body.challenge_id; item.tags_json = json.dumps(body.tags); item.updated_at = utcnow()
    db.commit(); db.refresh(item)
    return _note_payload(item)


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    item = db.get(Note, note_id)
    if not item: raise HTTPException(status_code=404, detail="Notebook entry not found.")
    db.delete(item); db.commit()
    return {"deleted": True}


@app.get("/api/achievements")
def achievements(db: Session = Depends(get_db)) -> dict[str, Any]:
    items = db.query(Achievement).order_by(Achievement.achieved_at.desc()).all()
    return {"items": [{"id": x.id, "title": x.title, "detail": x.detail, "achieved_at": _utc(x.achieved_at)} for x in items], "total": len(items)}


@app.post("/api/progress/reset")
def reset_all_progress(body: ConfirmBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.confirmation != "RESET ALL LEARNING PROGRESS":
        raise HTTPException(status_code=400, detail="Type RESET ALL LEARNING PROGRESS exactly to confirm.")
    db.query(ChallengeProgress).delete(synchronize_session=False)
    db.commit()
    return {"reset": True, "preserved": ["notes", "saved explanations", "workspace files", "completion history", "historical achievements"]}


@app.get("/api/data/export")
def export_progress_and_notes(db: Session = Depends(get_db)) -> Response:
    export = {"format": "redpanda-progress", "schema_version": 1,
              "exported_at": datetime.now(timezone.utc).isoformat(),
              "progress": [{"challenge_id": x.challenge_id, "state": x.state, "started_at": _utc(x.started_at), "completed_at": _utc(x.completed_at), "hint_level": x.hint_level, "latest_feedback": x.latest_feedback} for x in db.query(ChallengeProgress).all()],
              "achievements": [{"id": x.id, "title": x.title, "detail": x.detail, "achieved_at": _utc(x.achieved_at)} for x in db.query(Achievement).all()],
              "completion_history": [{"challenge_id": x.challenge_id, "completed_at": _utc(x.completed_at), "verification": json.loads(x.verification_json)} for x in db.query(CompletionHistory).all()],
              "notes": [_note_payload(x) for x in db.query(Note).all()],
              "preferences": {x.key: json.loads(x.value_json) for x in db.query(Preference).all()}}
    payload = json.dumps(export, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(payload, media_type="application/json", headers={"Content-Disposition": "attachment; filename=redpanda-progress-export.json"})


def _validate_export(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("format") != "redpanda-progress" or data.get("schema_version") != 1:
        raise ValueError("Unsupported progress export format or schema version.")
    limits = {"progress": 100, "achievements": 100, "completion_history": 5000, "notes": 5000}
    for key, limit in limits.items():
        value = data.get(key, [])
        if not isinstance(value, list) or len(value) > limit:
            raise ValueError(f"Invalid or oversized {key} collection.")
    manifests = {x["id"] for x in load_builtins()}
    for row in data.get("progress", []) + data.get("completion_history", []):
        if not isinstance(row, dict) or row.get("challenge_id") not in manifests and not str(row.get("challenge_id", "")).startswith("custom-"):
            raise ValueError("Progress export contains an unknown challenge identifier.")
    total = 0
    for note in data.get("notes", []):
        if not isinstance(note, dict) or note.get("kind") not in {"note", "explanation"} or not isinstance(note.get("title"), str) or not isinstance(note.get("content"), str):
            raise ValueError("Progress export contains an invalid notebook entry.")
        total += len(note["title"]) + len(note["content"])
    if total > 20_000_000:
        raise ValueError("Notebook export is too large.")
    preferences = data.get("preferences", {})
    if not isinstance(preferences, dict) or len(preferences) > 100:
        raise ValueError("Preferences collection is invalid.")
    return data


@app.post("/api/data/preview")
def preview_data_restore(body: DataPreviewBody) -> dict[str, Any]:
    try: data = _validate_export(body.data)
    except (ValueError, TypeError) as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"valid": True, "format": data["format"], "schema_version": data["schema_version"],
            "counts": {key: len(data.get(key, [])) for key in ("progress", "achievements", "completion_history", "notes")},
            "preference_count": len(data.get("preferences", {})),
            "secrets_included": False, "workspaces_included": False, "warning": "Workspace files and AI credentials are never included in this export."}


@app.post("/api/data/restore")
def restore_progress_and_notes(body: DataRestoreBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.confirmation != "RESTORE DATA":
        raise HTTPException(status_code=400, detail="Type RESTORE DATA exactly to confirm importing this export.")
    try: data = _validate_export(body.data)
    except (ValueError, TypeError) as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.mode == "replace":
        for model in (ChallengeProgress, Note, Preference):
            db.query(model).delete(synchronize_session=False)
        # Historical achievements and completion records are merged, not deleted by a data restore.
    for row in data.get("progress", []):
        item = db.get(ChallengeProgress, row["challenge_id"])
        if item is None: item = ChallengeProgress(challenge_id=row["challenge_id"]); db.add(item)
        item.state = row.get("state", "available") if row.get("state") in {"available", "in_progress", "completed"} else "available"
        item.started_at = _parse_dt(row.get("started_at")); item.completed_at = _parse_dt(row.get("completed_at")); item.hint_level = max(0, min(3, int(row.get("hint_level", 0)))); item.latest_feedback = str(row.get("latest_feedback") or "")[:1000] or None
    for row in data.get("notes", []):
        note_id = str(row.get("id") or uuid.uuid4())
        item = db.get(Note, note_id)
        if item is None: item = Note(id=note_id, kind=row["kind"], title=row["title"][:200], content=row["content"][:30000], challenge_id=row.get("challenge_id"), tags_json=json.dumps(row.get("tags", [])[:30])); db.add(item)
        elif body.mode == "replace":
            item.title = row["title"][:200]; item.content = row["content"][:30000]; item.kind = row["kind"]; item.challenge_id = row.get("challenge_id"); item.tags_json = json.dumps(row.get("tags", [])[:30]); item.updated_at = utcnow()
    for row in data.get("achievements", []):
        achievement_id = str(row.get("id", ""))[:100]
        if achievement_id and db.get(Achievement, achievement_id) is None: db.add(Achievement(id=achievement_id, title=str(row.get("title", "Imported achievement"))[:160], detail=str(row.get("detail", ""))[:2000]))
    for row in data.get("completion_history", []):
        db.add(CompletionHistory(challenge_id=row["challenge_id"], verification_json=json.dumps(row.get("verification", {}))[:10000]))
    for key, value in data.get("preferences", {}).items():
        if body.mode == "merge" and db.get(Preference, key): continue
        pref = db.get(Preference, key)
        if pref is None: pref = Preference(key=key, value_json=json.dumps(value)); db.add(pref)
        else: pref.value_json = json.dumps(value)
    db.commit()
    return {"restored": True, "mode": body.mode, "preserved": ["workspace contents", "AI credential file", "existing history and achievements"]}


def _parse_dt(value: str | None) -> datetime | None:
    if not value: return None
    try: return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError): return None


@app.post("/api/data/delete")
def delete_application_data(body: ConfirmBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.confirmation != "DELETE REDPANDA DATA":
        raise HTTPException(status_code=400, detail="Type DELETE REDPANDA DATA exactly to confirm this destructive action.")
    # Only registered challenge resources are eligible for cleanup, and each one is ownership-checked.
    workspace_ids = [row.challenge_id for row in db.query(WorkspaceRecord).all()]
    cleanup_errors: list[str] = []
    if workspace_ids:
        try:
            for challenge_id in workspace_ids:
                lab_manager.cleanup_registered_workspace(challenge_id, db)
        except Exception as exc:
            cleanup_errors.append(type(exc).__name__)
            raise HTTPException(status_code=500, detail={"message": "Could not verify and clean every registered workspace. Database records were preserved for recovery.", "errors": cleanup_errors}) from exc
    for model in (ChallengeProgress, Note, Achievement, CompletionHistory, Preference, ChallengeOverride):
        db.query(model).delete(synchronize_session=False)
    db.commit()
    ai.delete_settings()
    return {"deleted": True, "managed_workspaces_removed": len(workspace_ids), "unrelated_docker_resources_touched": False, "source_challenge_definitions_preserved": True}


@app.get("/api/builder")
def builder_list(db: Session = Depends(get_db)) -> dict[str, Any]:
    manifests = registry(db, include_disabled=True)
    disabled = {row.challenge_id for row in db.query(ChallengeOverride).filter(ChallengeOverride.disabled.is_(True)).all()}
    return {"items": [{**manifest, "is_custom": manifest["id"].startswith("custom-"), "disabled": manifest["id"] in disabled} for manifest in manifests], "built_in_count": len(load_builtins())}


def _validate_prereqs(manifest: dict[str, Any], db: Session) -> None:
    all_ids = {item["id"] for item in registry(db, include_disabled=True)} | {manifest["id"]}
    missing = set(manifest["prerequisites"]) - all_ids
    if missing: raise ValueError(f"Unknown prerequisite(s): {', '.join(sorted(missing))}")
    if manifest["id"] in manifest["prerequisites"]: raise ValueError("A challenge cannot depend on itself.")
    prospective = [item for item in registry(db, include_disabled=True) if item["id"] != manifest["id"]] + [manifest]
    from app.services.challenges import _check_prerequisite_cycles
    _check_prerequisite_cycles(prospective)


@app.post("/api/builder")
def create_custom_challenge(body: BuilderCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        manifest = validate_manifest(body.manifest, trusted_builtin=False)
        if not manifest["id"].startswith("custom-"):
            raise ValueError("Custom challenge IDs must begin with `custom-`.")
        if get_manifest(manifest["id"], db): raise ValueError("That challenge ID already exists.")
        manifest.pop("trusted_startup", None)
        manifest.pop("workspace_modes", None)
        _validate_prereqs(manifest, db)
    except (ValueError, Exception) as exc:
        # Pydantic errors are rendered as a concise validation response; no scripts are executed.
        raise HTTPException(status_code=422, detail=str(exc)[:1500]) from exc
    db.add(ChallengeOverride(challenge_id=manifest["id"], manifest_json=json.dumps(manifest), disabled=False, is_custom=True))
    db.commit()
    return {"saved": True, "manifest": manifest, "script_execution": "Custom scripts are not enabled in this build; only supported declarative validators run."}


@app.put("/api/builder/{challenge_id}")
def update_challenge(challenge_id: str, body: BuilderUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    base = _manifest_or_404(challenge_id, db)
    updates = body.model_dump(exclude_unset=True, exclude_none=True)
    candidate = {**base, **updates}
    try:
        candidate = validate_manifest(candidate, trusted_builtin=not challenge_id.startswith("custom-"))
        _validate_prereqs(candidate, db)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)[:1500]) from exc
    existing = db.get(ChallengeOverride, challenge_id)
    if challenge_id.startswith("custom-"):
        if existing is None: existing = ChallengeOverride(challenge_id=challenge_id, is_custom=True, disabled=False, manifest_json=json.dumps(candidate)); db.add(existing)
        else: existing.manifest_json = json.dumps(candidate)
    else:
        allowed_fields = ("title", "track", "difficulty", "summary", "description", "learning_objectives", "prerequisites", "tags", "offline_hints", "validation", "completion_explanation", "estimated_minutes")
        patch = {key: candidate[key] for key in allowed_fields if candidate[key] != load_builtins()[int(challenge_id[-2:])-1][key]}
        if existing is None: db.add(ChallengeOverride(challenge_id=challenge_id, manifest_json=json.dumps(patch), disabled=False, is_custom=False))
        else: existing.manifest_json = json.dumps(patch); existing.is_custom = False
    db.commit()
    return {"saved": True, "manifest": candidate}


@app.post("/api/builder/{challenge_id}/disable")
def disable_challenge(challenge_id: str, body: ConfirmBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    manifest = get_manifest(challenge_id, db)
    if not manifest: raise HTTPException(status_code=404, detail="Challenge not found.")
    if body.confirmation != challenge_id: raise HTTPException(status_code=400, detail=f"Type {challenge_id} to confirm disabling this challenge.")
    row = db.get(ChallengeOverride, challenge_id)
    if row is None: row = ChallengeOverride(challenge_id=challenge_id, manifest_json="{}", disabled=True, is_custom=challenge_id.startswith("custom-")); db.add(row)
    else: row.disabled = True
    db.commit()
    return {"disabled": True}


@app.delete("/api/builder/{challenge_id}")
def restore_challenge_defaults(challenge_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.get(ChallengeOverride, challenge_id)
    if not row: return {"restored": True, "changed": False}
    if row.is_custom:
        raise HTTPException(status_code=400, detail="Custom challenges cannot be restored to built-in defaults. Delete the custom challenge instead.")
    db.delete(row); db.commit()
    return {"restored": True, "changed": True}


@app.delete("/api/builder/{challenge_id}/delete")
def delete_custom_challenge(challenge_id: str, body: ConfirmBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.get(ChallengeOverride, challenge_id)
    if not row or not row.is_custom: raise HTTPException(status_code=404, detail="Custom challenge not found.")
    if body.confirmation != challenge_id: raise HTTPException(status_code=400, detail=f"Type {challenge_id} to delete this custom challenge.")
    if db.get(WorkspaceRecord, challenge_id):
        try: lab_manager.cleanup_registered_workspace(challenge_id, db)
        except Exception as exc: raise HTTPException(status_code=400, detail=f"Could not safely clean its workspace: {type(exc).__name__}") from exc
    db.delete(row); db.commit()
    return {"deleted": True, "notes_and_history_preserved": True}


@app.get("/api/packs/{challenge_id}/export")
def export_challenge_pack(challenge_id: str, db: Session = Depends(get_db)) -> Response:
    manifest = _manifest_or_404(challenge_id, db)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as pack:
        pack.writestr("challenge.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        pack.writestr("README.md", "# RedPanda Labs challenge pack\n\nThis pack contains one validated declarative challenge manifest. It contains no credentials, progress, workspace history, or executable scripts.\n")
    return Response(payload.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{challenge_id}-pack.zip"'})


async def _read_limited_body(request: Request, maximum_bytes: int) -> bytes:
    """Read an upload with an explicit cap, including requests without Content-Length."""
    header = request.headers.get("content-length")
    if header:
        try:
            if int(header) > maximum_bytes:
                raise HTTPException(status_code=413, detail=f"Request body exceeds the {maximum_bytes // (1024 * 1024)} MiB limit.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from None
    pieces: list[bytes] = []
    size = 0
    async for piece in request.stream():
        size += len(piece)
        if size > maximum_bytes:
            raise HTTPException(status_code=413, detail=f"Request body exceeds the {maximum_bytes // (1024 * 1024)} MiB limit.")
        pieces.append(piece)
    return b"".join(pieces)


def _read_pack(raw: bytes) -> dict[str, Any]:
    if len(raw) > 5 * 1024 * 1024: raise ValueError("Challenge pack exceeds the 5 MiB archive limit.")
    try: archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc: raise ValueError("The uploaded file is not a valid ZIP challenge pack.") from exc
    with archive:
        entries = archive.infolist()
        if len(entries) > 250: raise ValueError("Challenge pack contains too many files.")
        allowed = {"challenge.json", "README.md"}
        parsed: dict[str, Any] | None = None
        total = 0
        for info in entries:
            name = info.filename.rstrip("/")
            pure = PurePosixPath(name)
            if pure.is_absolute() or any(part in ("..", "") for part in pure.parts): raise ValueError("Unsafe path in challenge pack.")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000 or mode not in (0, 0o100000, 0o040000): raise ValueError("Challenge pack contains a link or unsupported file type.")
            if info.is_dir(): continue
            if name not in allowed: raise ValueError(f"Unsupported file in this build: {name}. Only challenge.json and README.md are accepted; custom scripts are not executed.")
            if info.file_size > 2 * 1024 * 1024: raise ValueError("Challenge-pack file is too large.")
            total += info.file_size
            if total > 4 * 1024 * 1024: raise ValueError("Challenge pack contents exceed 4 MiB.")
            if name == "challenge.json":
                parsed = json.loads(archive.read(info).decode("utf-8"))
        if parsed is None: raise ValueError("The ZIP must contain challenge.json at its root.")
    manifest = validate_manifest(parsed, trusted_builtin=False)
    if not manifest["id"].startswith("custom-"):
        manifest["id"] = "custom-" + manifest["id"].removeprefix("challenge-")
        manifest = validate_manifest(manifest, trusted_builtin=False)
    manifest.pop("trusted_startup", None); manifest.pop("workspace_modes", None)
    return manifest


@app.post("/api/packs/inspect")
async def inspect_challenge_pack(request: Request) -> dict[str, Any]:
    try:
        raw = await _read_limited_body(request, 5 * 1024 * 1024)
        manifest = _read_pack(raw)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)[:1200]) from exc
    return {"valid": True, "manifest": manifest, "contains_scripts": False, "secrets_included": False}


@app.post("/api/packs/import")
async def import_challenge_pack(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        raw = await _read_limited_body(request, 5 * 1024 * 1024)
        manifest = _read_pack(raw)
        _validate_prereqs(manifest, db)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)[:1200]) from exc
    existing = db.get(ChallengeOverride, manifest["id"])
    if existing and not existing.is_custom: raise HTTPException(status_code=409, detail="The imported challenge ID conflicts with a built-in challenge.")
    if existing is None: db.add(ChallengeOverride(challenge_id=manifest["id"], manifest_json=json.dumps(manifest), is_custom=True, disabled=False))
    else: existing.manifest_json = json.dumps(manifest); existing.disabled = False
    db.commit()
    return {"imported": True, "challenge_id": manifest["id"], "contains_executable_scripts": False}


@app.get("/api/ai/settings")
def get_ai_settings() -> dict[str, Any]:
    return ai.read_settings()


@app.put("/api/ai/settings")
def put_ai_settings(body: AISettingsBody) -> dict[str, Any]:
    try: return ai.save_settings(body.model_dump())
    except AIConfigurationError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/api/ai/settings")
def clear_ai_settings() -> dict[str, bool]:
    try: ai.delete_settings()
    except AIConfigurationError as exc: raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"deleted": True}


@app.post("/api/ai/test")
async def test_ai_connection() -> dict[str, Any]:
    try:
        answer = await ai.ask_ai([{"role":"system","content":"Reply with the single word READY. Do not include any secret or request metadata."}, {"role":"user","content":"Connectivity check. Reply READY."}], max_tokens=20)
        return {"connected": True, "message": "The provider returned a response.", "sample": answer[:80]}
    except AIConfigurationError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/mentor/ask")
async def mentor_ask(body: MentorBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    manifest = _manifest_or_404(body.challenge_id, db) if body.challenge_id else None
    if body.selected_output and not body.share_selected_output:
        raise HTTPException(status_code=400, detail="Selected terminal output was not shared. Confirm the preview before asking the AI to analyse it.")
    settings = ai.read_settings()
    if settings.get("configured"):
        messages = [{"role":"system","content":"You are RedPanda Labs' cybersecurity learning mentor. Teach with questions and progressive clues. Only discuss authorised local training systems. Never claim to execute commands. Never tell the application a challenge is complete; only its validator decides. Avoid revealing a full solution before the learner asks for detailed help."},
                    {"role":"user","content":json.dumps({"challenge": ({"title":manifest["title"],"description":manifest["description"],"objectives":manifest["learning_objectives"]} if manifest else None), "question":body.question, "explicitly_shared_terminal_output":body.selected_output if body.share_selected_output else None}, ensure_ascii=False)}]
        try: return {"answer": await ai.ask_ai(messages), "source": "configured-ai", "output_was_shared": bool(body.selected_output and body.share_selected_output)}
        except AIConfigurationError as exc: return {"answer": f"AI is unavailable: {exc}\n\nOffline guidance remains available in the mission's three hint levels.", "source": "offline-fallback", "output_was_shared": False}
    return {"answer": "Offline mentor mode is active, so no question or terminal output was transmitted. Start by stating what you expected, what you observed, and the smallest difference between them. Try the next mission hint or save your observation in the notebook. To use a compatible AI model, configure a provider in Settings.", "source": "offline", "output_was_shared": False}


@app.post("/api/mentor/explain")
async def explain_text(body: ExplainBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    manifest = _manifest_or_404(body.challenge_id, db) if body.challenge_id else None
    settings = ai.read_settings()
    if body.use_ai and settings.get("configured"):
        if not body.share_confirmed:
            raise HTTPException(status_code=400, detail="Review the selected text and confirm before sending it to the configured AI provider.")
        prompt = [{"role":"system","content":"Explain technical commands/output for a beginner. Cover what it does, components, likely output, common mistakes, side effects, and safety. Do not execute the text."},
                  {"role":"user","content":json.dumps({"challenge":manifest["title"] if manifest else None,"selected_text":body.text}, ensure_ascii=False)}]
        try: return {"explanation": await ai.ask_ai(prompt, max_tokens=1000), "source": "configured-ai"}
        except AIConfigurationError as exc: return {"explanation": _offline_explanation(body.text, str(exc)), "source": "offline-fallback"}
    return {"explanation": _offline_explanation(body.text, "AI was not used; your selected text stayed local."), "source": "offline"}


def _offline_explanation(value: str, note: str) -> str:
    first = value.strip().splitlines()[0][:240] if value.strip() else "(empty)"
    command = first.split()[0] if first else ""
    references = {
        "pwd": "Prints the current working directory. It reports a location and does not change files.",
        "whoami": "Prints the effective username of the current process. It is an observation command.",
        "ls": "Lists directory entries. Add `-a` to include dot-prefixed hidden names and `-l` for detailed metadata.",
        "find": "Walks a directory tree and applies tests to each entry. Restrict its starting path to the workspace while learning.",
        "grep": "Searches text for lines matching a pattern. Check whether the pattern is literal or a regular expression.",
        "chmod": "Changes permission bits on a file or directory. It mutates access settings, so verify the target path before running it.",
        "kill": "Sends a signal to a process ID. Confirm the PID belongs to the intended lab process before signalling it.",
        "curl": "Makes a client request to a URL and prints the response. The HTTP status and headers help distinguish transport from application results.",
        "python3": "Runs the Python interpreter. A script may read or modify files, so inspect code before executing unfamiliar material.",
        "cat": "Prints file contents to standard output. Avoid dumping secrets into shared or remote conversations.",
        "stat": "Shows file metadata such as mode, owner, and timestamps. It reads metadata without changing the file.",
    }
    explanation = references.get(command, "Treat the selected text as input to investigate, not something to execute blindly. Identify its source, arguments, expected output, and whether it changes state.")
    return f"**Selected text:** `{first}`\n\n{explanation}\n\n**Privacy:** {note}"


@app.post("/api/workspaces/{challenge_id}/archive")
def archive_workspace(challenge_id: str, body: ConfirmBody) -> Response:
    if body.confirmation != challenge_id: raise HTTPException(status_code=400, detail=f"Type {challenge_id} to archive this workspace.")
    try: content = lab_manager.export_workspace(challenge_id)
    except LabUnavailable as exc: raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc: raise HTTPException(status_code=400, detail=f"Workspace archive failed: {type(exc).__name__}") from exc
    return Response(content, media_type="application/x-tar", headers={"Content-Disposition": f'attachment; filename="{challenge_id}-workspace.tar"'})


@app.put("/api/workspaces/{challenge_id}/archive")
async def restore_workspace_archive(challenge_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    # The raw request body is a tar stream; X-Confirm-Workspace is an explicit confirmation.
    if request.headers.get("x-confirm-workspace") != challenge_id: raise HTTPException(status_code=400, detail=f"Set X-Confirm-Workspace: {challenge_id} to confirm restoring this workspace archive.")
    _manifest_or_404(challenge_id, db)
    raw = await _read_limited_body(request, 10 * 1024 * 1024)
    try: lab_manager.restore_workspace(challenge_id, raw)
    except LabUnavailable as exc: raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc: raise HTTPException(status_code=422, detail=f"Workspace archive rejected: {str(exc)[:500]}") from exc
    return {"restored": True, "challenge_id": challenge_id, "secrets_included": False}


@app.websocket("/api/terminal/{challenge_id}")
async def terminal_socket(websocket: WebSocket, challenge_id: str):
    origin = websocket.headers.get("origin")
    host = (websocket.headers.get("host") or "").split(":", 1)[0].lower()
    if host not in ALLOWED_HOSTS or (origin and origin not in ALLOWED_ORIGINS):
        await websocket.close(code=1008, reason="Local application origin required")
        return
    db_session = next(get_db())
    try:
        manifest = get_manifest(challenge_id, db_session)
        if manifest is None:
            await websocket.close(code=1008, reason="Unknown challenge")
            return
        try:
            progress_map = {row.challenge_id for row in db_session.query(ChallengeProgress).filter(ChallengeProgress.completed_at.is_not(None)).all()}
            if any(item not in progress_map for item in manifest["prerequisites"]):
                await websocket.close(code=1008, reason="Prerequisites are locked")
                return
            workspace = lab_manager.ensure_workspace(manifest, db_session)
            progress = _get_or_create_progress(challenge_id, db_session)
            if progress.state != "completed" and not progress.completed_at:
                progress.state = "in_progress"
                progress.started_at = progress.started_at or utcnow()
                db_session.commit()
        except (LabUnavailable, ResourceOwnershipError, RuntimeError, ValueError) as exc:
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=1011)
            return
        await websocket.accept()
        session, created = await terminal_manager.get_or_start(challenge_id, workspace["container_name"])
        session.subscribers += 1
        await websocket.send_json({"type":"ready", "created":created, "message":"Connected to the real Bash shell inside the lab container."})
        tail = session.tail()
        if tail:
            await websocket.send_json({"type":"output", "data":tail.decode("utf-8", "replace")})
        output_task = asyncio.create_task(_terminal_output_loop(websocket, session))
        try:
            while True:
                message = await websocket.receive_text()
                try: event = json.loads(message)
                except json.JSONDecodeError: event = {"type":"input", "data":message}
                kind = event.get("type")
                if kind == "input" and isinstance(event.get("data"), str) and len(event["data"]) <= 12000:
                    session.write(event["data"])
                elif kind == "resize":
                    session.resize(event.get("rows", 28), event.get("cols", 100))
                elif kind == "ping":
                    await websocket.send_json({"type":"pong"})
        except WebSocketDisconnect:
            pass
        finally:
            session.subscribers = max(0, session.subscribers - 1)
            output_task.cancel()
            try: await output_task
            except asyncio.CancelledError: pass
    except RuntimeError as exc:
        logger.info("Terminal connection ended: %s", type(exc).__name__)
        try: await websocket.close(code=1011)
        except Exception: pass
    finally:
        db_session.close()


async def _terminal_output_loop(websocket: WebSocket, session) -> None:
    while True:
        data = await session.output_queue.get()
        await websocket.send_json({"type":"output", "data":data.decode("utf-8", "replace")})


_FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@app.get("/{path:path}", include_in_schema=False)
def frontend_fallback(path: str):
    if path.startswith("api/") or path == "api":
        raise HTTPException(status_code=404, detail="API route not found.")
    index = _FRONTEND_DIST / "index.html"
    if not index.exists():
        return JSONResponse({"detail": "Frontend build not found. Run `npm ci && npm run build` in the frontend directory, or use `npm run dev` during development."}, status_code=503)
    requested = (_FRONTEND_DIST / path).resolve()
    try: requested.relative_to(_FRONTEND_DIST.resolve())
    except ValueError: raise HTTPException(status_code=404, detail="Not found.")
    if path and requested.is_file(): return FileResponse(requested)
    return FileResponse(index)
