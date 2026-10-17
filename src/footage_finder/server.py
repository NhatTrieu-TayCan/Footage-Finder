"""FastAPI REST and Real-Time SSE Server for Footage Finder."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from footage_finder.cache import DiskCache
from footage_finder.config import Settings, load_domain_blocklist, load_pricing
from footage_finder.intent.generator import IntentGenerator
from footage_finder.models import SegmentReport
from footage_finder.report.csv_generator import export_reports_to_csv, read_selected_csv
from footage_finder.report.downloader import AssetDownloader
from footage_finder.report.html_generator import generate_html_report
from footage_finder.report.json_generator import export_reports_to_json
from footage_finder.rerank.gemini_vision import GeminiVisionReranker
from footage_finder.search.manager import SearchManager
from footage_finder.segmenter.chunker import chunk_script, filter_segments_range
from footage_finder.tracker import CostTracker

app = FastAPI(title="Footage Finder Studio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount outputs for serving local thumbs and full images
output_dir = Path("output")
output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/output", StaticFiles(directory=str(output_dir)), name="output")

# In-memory job tracker for SSE
class JobState:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.is_done = False
        self.result: dict[str, Any] | None = None
        self.error: str | None = None

    async def emit(self, event_type: str, data: dict[str, Any]):
        await self.queue.put({"type": event_type, "data": data, "timestamp": datetime.now().isoformat()})

JOBS: dict[str, JobState] = {}


class RunRequest(BaseModel):
    script_text: str
    script_name: str = "Script"
    mock: bool = False
    youtube: bool = False
    prefer_aspect: str = "16:9"
    min_score: float = 6.0
    segments_range: str | None = None
    resume: bool = True


async def _run_pipeline_job(job: JobState, req: RunRequest):
    """Executes the pipeline while streaming events into the job's queue."""
    settings = Settings()
    if req.prefer_aspect:
        settings.prefer_aspect = req.prefer_aspect
    if req.min_score is not None:
        settings.min_score = req.min_score

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = "".join(c if c.isalnum() else "_" for c in req.script_name).strip("_") or "script"
    run_dir = Path(f"output/{clean_name}_{timestamp}")
    thumbs_dir = run_dir / "thumbs"
    full_images_dir = run_dir / "full_images"
    run_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    full_images_dir.mkdir(parents=True, exist_ok=True)

    tracker = CostTracker(pricing_dict=load_pricing(settings.pricing_file))
    blocklist = load_domain_blocklist(settings.blocklist_file)
    cache = DiskCache()

    await job.emit("progress", {
        "step": "init",
        "message": f"Initializing pipeline for '{req.script_name}' (Mock: {req.mock})...",
        "run_id": run_dir.name
    })

    try:
        # Step 1: Parse and Chunk Script
        all_segments = chunk_script(req.script_text)
        target_segments = filter_segments_range(all_segments, req.segments_range) if req.segments_range else all_segments
        if not target_segments:
            raise ValueError(f"No segments matched range '{req.segments_range}'")

        await job.emit("progress", {
            "step": "parsed_segments",
            "message": f"Parsed {len(target_segments)} visual beats (segments)",
            "segments": [s.model_dump() for s in target_segments],
            "total_segments": len(target_segments)
        })

        # Step 2: Intent Generation
        intent_gen = IntentGenerator(
            settings=settings,
            cache=cache if req.resume else DiskCache(base_dir=run_dir / ".temp_cache"),
            tracker=tracker,
            mock=req.mock,
        )

        await job.emit("progress", {
            "step": "intent_start",
            "message": "Generating visual research intents with Gemini...",
        })

        intents = await intent_gen.generate_all_intents(
            segments=target_segments, full_script=req.script_text, batch_size=5
        )

        for seg, intent in zip(target_segments, intents):
            await job.emit("intent_generated", {
                "segment_id": seg.id,
                "intent": intent.model_dump(),
            })

        # Step 3: Search & Evaluation Setup
        search_mgr = SearchManager(
            settings=settings,
            domain_blocklist=blocklist,
            cache=cache if req.resume else DiskCache(base_dir=run_dir / ".temp_cache"),
            tracker=tracker,
            mock=req.mock,
            enable_youtube=req.youtube,
        )

        reranker = GeminiVisionReranker(
            settings=settings,
            cache=cache if req.resume else DiskCache(base_dir=run_dir / ".temp_cache"),
            tracker=tracker,
            mock=req.mock,
        )

        reports: list[SegmentReport] = []

        # Step 4: Process Each Segment
        for idx, (seg, intent) in enumerate(zip(target_segments, intents), start=1):
            await job.emit("segment_start", {
                "segment_id": seg.id,
                "index": idx,
                "total": len(target_segments),
                "message": f"Searching candidates for {seg.id} ({idx}/{len(target_segments)})...",
            })

            # Search & Filter
            candidates, l1_drops, l2_drops, phash_drops = await search_mgr.gather_and_filter_candidates(
                queries=intent.queries,
                image_types=intent.image_types,
                thumbs_dir=thumbs_dir,
                max_candidates=settings.candidates_per_segment,
            )

            await job.emit("segment_candidates_found", {
                "segment_id": seg.id,
                "count": len(candidates),
                "l1_dropped": l1_drops,
                "l2_dropped": l2_drops,
                "phash_dropped": phash_drops,
                "candidates": [c.model_dump() for c in candidates],
            })

            # Vision Rerank & Layer 3 Watermark Check
            await job.emit("segment_evaluating", {
                "segment_id": seg.id,
                "message": f"Running Gemini Vision ranking & Layer 3 watermark defense on {len(candidates)} images...",
            })

            report = await reranker.rerank_and_filter_segment(
                segment=seg,
                intent=intent,
                candidates=candidates,
                full_images_dir=full_images_dir,
            )
            reports.append(report)

            await job.emit("segment_completed", {
                "segment_id": seg.id,
                "status": report.status,
                "top_picks_count": len(report.top_picks),
                "alternates_count": len(report.alternates),
                "report": report.model_dump(),
            })

        # Step 5: Finalize Reports
        html_path = run_dir / "report.html"
        csv_path = run_dir / "report.csv"
        json_path = run_dir / "report.json"

        stats = tracker.stats
        generate_html_report(reports, html_path, script_title=req.script_name, stats=stats)
        export_reports_to_csv(reports, csv_path)
        export_reports_to_json(reports, json_path, stats=stats, script_name=req.script_name)

        final_data = {
            "run_id": run_dir.name,
            "script_name": req.script_name,
            "html_path": str(html_path),
            "csv_path": str(csv_path),
            "json_path": str(json_path),
            "stats": stats.model_dump(),
            "reports": [r.model_dump() for r in reports],
        }

        job.result = final_data
        job.is_done = True
        await job.emit("pipeline_finished", final_data)

    except Exception as e:  # noqa: BLE001
        job.error = str(e)
        job.is_done = True
        await job.emit("pipeline_error", {"error": str(e)})


@app.post("/api/run")
async def start_run(req: RunRequest, background_tasks: BackgroundTasks):
    """Start an asynchronous Footage Finder run."""
    job_id = str(uuid.uuid4())
    job = JobState(job_id)
    JOBS[job_id] = job
    background_tasks.add_task(_run_pipeline_job, job, req)
    return {"job_id": job_id}


@app.get("/api/stream/{job_id}")
async def stream_job(job_id: str):
    """Stream real-time Server-Sent Events (SSE) for a running job."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    job = JOBS[job_id]

    async def event_generator():
        while True:
            try:
                # Wait for next event with a 15-second heartbeat
                event = await asyncio.wait_for(job.queue.get(), timeout=15.0)
                yield {
                    "event": event["type"],
                    "data": json.dumps(event),
                }
                if event["type"] in ("pipeline_finished", "pipeline_error"):
                    break
            except TimeoutError:
                if job.is_done:
                    break
                yield {"event": "ping", "data": json.dumps({"type": "ping"})}

    return EventSourceResponse(event_generator())


@app.get("/api/runs")
async def list_runs():
    """List all completed runs in output/."""
    runs = []
    if not output_dir.exists():
        return {"runs": []}

    for path in sorted(output_dir.iterdir(), reverse=True):
        if path.is_dir() and not path.name.startswith("."):
            report_json = path / "report.json"
            meta: dict[str, Any] = {
                "run_id": path.name,
                "has_html": (path / "report.html").exists(),
                "has_csv": (path / "report.csv").exists(),
                "has_json": report_json.exists(),
                "timestamp": path.name.split("_")[-2] if "_" in path.name else "",
            }
            if report_json.exists():
                try:
                    data = json.loads(report_json.read_text(encoding="utf-8"))
                    meta["script_name"] = data.get("script_name")
                    meta["total_segments"] = data.get("total_segments")
                    meta["stats"] = data.get("stats")
                except (json.JSONDecodeError, OSError):
                    continue
            runs.append(meta)
    return {"runs": runs}


@app.get("/api/runs/{run_id}")
async def get_run_details(run_id: str):
    """Get full report data for a completed run."""
    run_path = output_dir / run_id
    if not run_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    report_json = run_path / "report.json"
    if report_json.exists():
        return json.loads(report_json.read_text(encoding="utf-8"))

    # Fallback to CSV if json was not generated yet
    report_csv = run_path / "report.csv"
    if report_csv.exists():
        rows = read_selected_csv(report_csv)
        return {"run_id": run_id, "rows": rows}

    raise HTTPException(status_code=404, detail="No report found in run directory")


class DownloadSelectedRequest(BaseModel):
    run_id: str
    items: list[dict[str, Any]]
    dest_dir: str = "downloads"


@app.post("/api/download")
async def download_selected_assets(req: DownloadSelectedRequest):
    """Download selected images organized into segment folders ready for DaVinci Resolve."""
    settings = Settings()
    dest_path = Path(req.dest_dir) / req.run_id
    dest_path.mkdir(parents=True, exist_ok=True)

    downloader = AssetDownloader(
        user_agent=settings.wikimedia_user_agent,
        download_dir=dest_path,
        concurrency=settings.concurrent_download_limit,
    )

    # Group by segment ID
    segments_map: dict[str, list[dict]] = {}
    for r in req.items:
        sid = r.get("segment_id", "S000")
        segments_map.setdefault(sid, []).append(r)

    import httpx
    client = httpx.AsyncClient(timeout=25.0)
    consolidated_credits: list[str] = [
        "===========================================================",
        f"FOOTAGE FINDER - ATTRIBUTION & CREDITS ({req.run_id})",
        "Paste necessary lines into your YouTube video description",
        "===========================================================\n",
    ]

    try:
        tasks = []
        for sid, items in segments_map.items():
            seg_folder = dest_path / sid
            for idx, row in enumerate(items, start=1):
                tasks.append(downloader.download_asset(row, seg_folder, idx, client))

        results = await asyncio.gather(*tasks)
        for ok, credit_line in results:
            if ok and credit_line:
                consolidated_credits.append(credit_line)

        credits_file = dest_path / "credits.txt"
        credits_file.write_text("\n".join(consolidated_credits) + "\n", encoding="utf-8")
    finally:
        await client.aclose()

    return {
        "status": "success",
        "download_dir": str(dest_path),
        "credits_file": str(dest_path / "credits.txt"),
        "credits_text": "\n".join(consolidated_credits),
    }


@app.get("/api/config")
async def get_config():
    """Return system configuration and current model defaults."""
    settings = Settings()
    return {
        "gemini_text_model": settings.gemini_text_model,
        "gemini_vision_model": settings.gemini_vision_model,
        "has_gemini_key": bool(settings.gemini_api_key),
        "has_serper_key": bool(settings.serper_api_key),
        "has_youtube_key": bool(settings.youtube_api_key),
        "prefer_aspect": settings.prefer_aspect,
        "min_score": settings.min_score,
        "candidates_per_segment": settings.candidates_per_segment,
    }


# Mount built React/Vite frontend if available
frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

