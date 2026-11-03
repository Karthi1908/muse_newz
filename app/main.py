from __future__ import annotations
import base64
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from typing import Any, List, Optional
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from config.settings import settings
from app.agents.topic_agent import TopicEditorAgent
from app.models.schemas import CadenceType, ReaderProfile, WeekdayType
from app.services.formatter import NewspaperFormatterService
from app.services.runner import EditionPipelineRunner
from app.services.scheduler import NewspaperSchedulerService
from app.services.storage import StorageService
from app.services.stt import SpeechToTextService
from app.services.token_compiler import compile_tokens_css
from scripts.seed_sample_archive import ensure_sample_archive_seeded


storage = StorageService()
runner = EditionPipelineRunner(storage=storage)
scheduler = NewspaperSchedulerService(storage=storage, runner=runner)
formatter = NewspaperFormatterService()
topic_agent = TopicEditorAgent()
stt_service = SpeechToTextService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    compile_tokens_css()
    await ensure_sample_archive_seeded(storage=storage)
    # Serverless runtimes freeze background threads; run APScheduler only outside serverless
    if os.getenv("VERCEL") != "1":
        scheduler.start_background_scheduler()
    yield
    if os.getenv("VERCEL") != "1":
        scheduler.stop_background_scheduler()


app = FastAPI(
    title="Your Daily Muse",
    version="1.0.0",
    description="Autonomous Verification-First Personalized Newspaper (Google ADK + Meta Muse Model API)",
    lifespan=lifespan,
)

static_dir = settings.BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


_PROFILE_COOKIE = "muse_reader"


def _encode_profile_cookie(profile: ReaderProfile) -> str:
    raw = json.dumps(profile.model_dump(mode="json"), separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_profile_cookie(value: str) -> Optional[ReaderProfile]:
    try:
        data = json.loads(base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8"))
        return ReaderProfile(**data)
    except Exception:
        return None


@app.middleware("http")
async def hydrate_reader_profile_from_cookie(request: Request, call_next):
    """
    Serverless (Vercel) instances each have their own ephemeral /tmp SQLite copy, so a profile saved on one
    instance is invisible to the next. The reader profile is therefore mirrored in a browser cookie and
    re-applied to the local store at the start of every request.
    """
    if os.getenv("VERCEL") == "1" and not request.url.path.startswith("/static"):
        cookie_val = request.cookies.get(_PROFILE_COOKIE)
        if cookie_val:
            profile = _decode_profile_cookie(cookie_val)
            if profile is not None and request.url.path != "/api/topics/confirm":
                try:
                    storage.save_reader_profile(profile)
                except Exception:
                    pass
    return await call_next(request)


class TopicProposeRequest(BaseModel):
    command: str
    replace_target: Optional[str] = None


class TopicConfirmRequest(BaseModel):
    reader_name: str = ""
    topics: List[str]
    geographic_preference: str = "Global"


class ScheduleUpdateRequest(BaseModel):
    cadence: CadenceType = "daily"
    start_time_local: str = "07:00"
    weekly_weekday: Optional[WeekdayType] = "SUN"
    time_zone: str = "UTC"
    paused: bool = False
    demo_mode: bool = False


@app.get("/", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
async def read_newspaper_home(
    request: Request,
    edition_id: Optional[str] = Query(default=None),
) -> HTMLResponse:
    if not storage.list_editions():
        await ensure_sample_archive_seeded(storage=storage)

    edition = storage.get_edition(edition_id) if edition_id else storage.get_latest_edition()
    if edition is None:
        edition = await runner.execute_edition_build(trigger_type="manual")
    else:
        from app.services.formatter import normalize_edition_layout_and_centrepiece
        edition, was_upgraded = normalize_edition_layout_and_centrepiece(edition)
        if was_upgraded:
            standalone_html = formatter.render_standalone_html(edition)
            storage.save_published_edition(edition=edition, standalone_html=standalone_html)

    # Clear "new edition available" indicator once reader views the paper
    storage.update_schedule_state(new_edition_available=False)

    reader = storage.get_reader_profile()
    sched = storage.get_schedule_state()
    archive_list = storage.list_editions()

    tokens_css_path = settings.BASE_DIR / "app" / "static" / "css" / f"tokens.v{edition.design_version.split('.')[0]}.css"
    if not tokens_css_path.exists():
        compile_tokens_css()
    tokens_css = tokens_css_path.read_text(encoding="utf-8")
    newspaper_css = (settings.BASE_DIR / "app" / "static" / "css" / "newspaper.css").read_text(encoding="utf-8")

    from app.services.formatter import _inline_static_images
    tmpl = formatter.env.get_template("app_shell.html")
    html_out = tmpl.render(
        edition=edition,
        reader=reader,
        schedule=sched,
        archive_list=archive_list,
        retention_limit=settings.ARCHIVE_RETENTION_LIMIT,
        inlined_tokens_css=tokens_css,
        inlined_newspaper_css=newspaper_css,
    )
    return HTMLResponse(
        content=_inline_static_images(html_out),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/api/status")
@app.get("/status")
async def get_newsroom_status() -> dict[str, Any]:
    return {
        "schedule": storage.get_schedule_state().model_dump(mode="json"),
        "active_run": storage.get_active_or_latest_run(),
        "reader": storage.get_reader_profile().model_dump(mode="json"),
    }


@app.get("/api/editions")
@app.get("/editions")
async def list_archive_editions(format: Optional[str] = Query(default=None)) -> dict[str, Any]:
    items = storage.list_editions(format_filter=format)
    return {
        "editions": items,
        "retention_limit": settings.ARCHIVE_RETENTION_LIMIT,
    }


@app.get("/api/editions/{edition_id}")
@app.get("/editions/{edition_id}")
async def get_single_edition(edition_id: str) -> dict[str, Any]:
    ed = storage.get_edition(edition_id)
    if not ed:
        raise HTTPException(status_code=404, detail="Edition not found")
    return ed.model_dump(mode="json")


@app.get("/api/editions/{edition_id}/images/{filename}")
@app.get("/editions/{edition_id}/images/{filename}")
async def get_edition_image(edition_id: str, filename: str) -> FileResponse:
    img_path = settings.EDITIONS_DIR / edition_id / "images" / filename
    if not img_path.exists():
        cache_img = settings.DATA_DIR / "demo_cache" / "images" / filename
        if cache_img.exists():
            return FileResponse(path=str(cache_img), media_type="image/png")
        raise HTTPException(status_code=404, detail="Illustration image not found")
    return FileResponse(path=str(img_path), media_type="image/png")


@app.get("/api/editions/{edition_id}/download")
async def download_standalone_edition(edition_id: str) -> FileResponse:
    ed = storage.get_edition(edition_id)
    if not ed:
        raise HTTPException(status_code=404, detail="Edition not found")
    html_str = formatter.render_standalone_html(ed)
    p = settings.EDITIONS_DIR / edition_id / f"{edition_id}_standalone.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    safe_pub = ed.publication_title.replace(" ", "_")
    return FileResponse(
        path=str(p),
        media_type="text/html",
        filename=f"{safe_pub}_No_{ed.edition_number}_{ed.format_label}.html",
    )


@app.post("/api/editions/generate-now")
async def trigger_generate_now() -> JSONResponse:
    result = await scheduler.trigger_build(trigger_type="manual")
    return JSONResponse(content=result)


@app.post("/api/topics/propose")
async def propose_topic_change(req: TopicProposeRequest) -> dict[str, Any]:
    reader = storage.get_reader_profile()
    proposal = await topic_agent.propose_topic_change(
        current_topics=reader.topics,
        user_command=req.command,
        replace_target=req.replace_target,
        current_geographic_preference=reader.geographic_preference,
    )
    return proposal.model_dump(mode="json")


@app.post("/api/topics/voice")
async def voice_topic_change(
    audio: UploadFile = File(...),
    fallback_hint: str = Form(default=""),
) -> dict[str, Any]:
    raw_bytes = await audio.read()
    ok, transcript, stt_msg = await stt_service.transcribe_audio(
        audio_bytes=raw_bytes,
        filename=audio.filename or "voice.webm",
        fallback_hint=fallback_hint,
    )
    reader = storage.get_reader_profile()
    if not ok:
        return {
            "status": "unclear",
            "stt_message": stt_msg,
            "proposal": {
                "transcript_or_input": "",
                "current_topics": reader.topics,
                "proposed_topics": reader.topics,
                "current_geographic_preference": reader.geographic_preference,
                "proposed_geographic_preference": None,
                "requires_replacement_choice": False,
                "assistant_message": stt_msg,
                "unclear_audio": True,
            },
        }
    proposal = await topic_agent.propose_topic_change(
        current_topics=reader.topics,
        user_command=transcript,
        current_geographic_preference=reader.geographic_preference,
    )
    return {
        "status": "ok",
        "stt_message": stt_msg,
        "proposal": proposal.model_dump(mode="json"),
    }


@app.post("/api/topics/confirm")
async def confirm_topics(req: TopicConfirmRequest) -> dict[str, Any]:
    current = storage.get_reader_profile()
    clean_name = req.reader_name.strip() or "Muse"
    updated = ReaderProfile(
        reader_name=clean_name,
        time_zone=current.time_zone,
        topics=req.topics,
        geographic_preference=req.geographic_preference.strip() or current.geographic_preference,
    )
    try:
        storage.save_reader_profile(updated)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Could not save topics: {exc}"})

    # Also update the latest edition's masthead reader_name & geographic_preference so reload shows the new title immediately
    # (best-effort: a failure here must never block saving the topics themselves)
    try:
        latest_ed = storage.get_latest_edition()
        if latest_ed is not None:
            latest_ed.reader_name = updated.reader_name
            latest_ed.geographic_preference = updated.geographic_preference
            standalone_html = formatter.render_standalone_html(latest_ed)
            storage.save_published_edition(edition=latest_ed, standalone_html=standalone_html)
    except Exception:
        pass

    response = JSONResponse(
        content={
            "status": "saved",
            "reader": {
                **updated.model_dump(mode="json"),
                "publication_title": updated.publication_title,
                "publication_tagline": updated.publication_tagline,
            },
        }
    )
    response.set_cookie(
        _PROFILE_COOKIE,
        _encode_profile_cookie(updated),
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=os.getenv("VERCEL") == "1",
        path="/",
    )
    return response


@app.post("/api/schedule/preview")
async def preview_schedule(req: ScheduleUpdateRequest) -> dict[str, Any]:
    next_due = scheduler.compute_next_due_time(
        cadence=req.cadence,
        start_time_local=req.start_time_local,
        time_zone_str=req.time_zone,
        weekly_weekday=req.weekly_weekday,
        demo_mode=req.demo_mode,
    )
    fmt_name = runner.format_resolver.cadence_to_format_name(req.cadence)
    fmt_spec = runner.format_resolver.get_format_spec(fmt_name)
    return {
        "cadence": req.cadence,
        "format_name": fmt_name,
        "format_label": fmt_spec["label"],
        "next_due_at": next_due.isoformat(),
    }


@app.post("/api/schedule")
async def save_schedule(req: ScheduleUpdateRequest) -> dict[str, Any]:
    state = scheduler.configure_schedule(
        cadence=req.cadence,
        start_time_local=req.start_time_local,
        time_zone=req.time_zone,
        weekly_weekday=req.weekly_weekday,
        paused=req.paused,
        demo_mode=req.demo_mode,
    )
    return state.model_dump(mode="json")
