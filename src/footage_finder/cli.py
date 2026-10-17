"""Typer CLI entrypoint for Footage Finder."""

from __future__ import annotations

import asyncio
import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from footage_finder.cache import DiskCache
from footage_finder.config import Settings, validate_gemini_models_or_fail
from footage_finder.intent.generator import IntentGenerator
from footage_finder.models import SegmentReport
from footage_finder.report.csv_generator import export_reports_to_csv
from footage_finder.report.downloader import AssetDownloader
from footage_finder.report.html_generator import generate_html_report
from footage_finder.rerank.gemini_vision import GeminiVisionReranker
from footage_finder.search.manager import SearchManager
from footage_finder.segmenter.chunker import chunk_script, filter_segments_range
from footage_finder.segmenter.parser import parse_script_file
from footage_finder.tracker import CostTracker

app = typer.Typer(
    name="footage-finder",
    help="Script-to-Image Footage Finder for faceless YouTube documentary workflows.",
    add_completion=False,
)
console = Console()


@app.command()
def run(
    script: Path = typer.Argument(..., help="Path to narration script (.txt or .docx)"),
    mock: bool = typer.Option(
        False, "--mock", help="Run with deterministic offline mock fixtures (zero API calls & $0 cost)"
    ),
    youtube: bool = typer.Option(
        False, "--youtube", help="Enable YouTube Data API v3 search for video footage leads"
    ),
    resume: bool = typer.Option(
        True, "--resume/--no-resume", help="Resume from disk cache for previously fetched items"
    ),
    segments: str | None = typer.Option(
        None, "--segments", help="Filter segment range to process (e.g. 'S001-S005' or 'S003')"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Custom output directory for reports and media"
    ),
):
    """Run full Footage Finder pipeline: segment, intent, search, filter, vision rerank, report."""
    settings = Settings()
    tracker = CostTracker()
    cache = DiskCache()

    console.print(
        Panel.fit(
            f"[bold cyan]Footage Finder[/bold cyan] - Script-to-Image Research Engine\n"
            f"Script: [yellow]{script}[/yellow] | Mode: [bold]{'MOCK (Offline)' if mock else 'LIVE (Gemini API)'}[/bold]",
            border_style="cyan",
        )
    )

    # 1. Model & API Key Validation
    if not mock:
        if not settings.gemini_api_key:
            console.print(
                "[bold red]Error:[/bold red] GEMINI_API_KEY is not set in environment or .env!\n"
                "Please configure GEMINI_API_KEY or run with --mock for offline mode."
            )
            raise typer.Exit(code=1)

        from google import genai

        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            validate_gemini_models_or_fail(
                client=client,
                text_model=settings.gemini_text_model,
                vision_model=settings.gemini_vision_model,
            )
            console.print(
                f"[green]✓ Verified Gemini models:[/green] text='{settings.gemini_text_model}', vision='{settings.gemini_vision_model}'"
            )
        except (RuntimeError, ValueError, OSError) as e:
            console.print(f"[bold red]Model validation error:[/bold red] {e}")
            raise typer.Exit(code=1)
    else:
        client = None

    # 2. Parse & Segment Script
    try:
        raw_script = parse_script_file(script)
        all_segments = chunk_script(raw_script)
        if segments:
            target_segments = filter_segments_range(all_segments, segments)
            console.print(
                f"[cyan]Filtered segments:[/cyan] {len(target_segments)} of {len(all_segments)} matching range '{segments}'"
            )
        else:
            target_segments = all_segments
            console.print(f"[cyan]Parsed script:[/cyan] {len(target_segments)} visual beats (segments)")
    except (FileNotFoundError, ValueError, OSError) as e:
        console.print(f"[bold red]Failed to parse script:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Setup Output Directory
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    script_stem = script.stem
    run_dir = output_dir or Path(f"output/{script_stem}_{timestamp_str}")
    thumbs_dir = run_dir / "thumbs"
    full_images_dir = run_dir / "full_images"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Initialize Engine Components
    intent_gen = IntentGenerator(
        settings=settings,
        cache=cache if resume else DiskCache(base_dir=run_dir / ".temp_cache"),
        tracker=tracker,
        client=client,
        mock=mock,
    )
    search_mgr = SearchManager(
        settings=settings,
        cache=cache if resume else DiskCache(base_dir=run_dir / ".temp_cache"),
        tracker=tracker,
    )
    reranker = GeminiVisionReranker(
        settings=settings,
        cache=cache if resume else DiskCache(base_dir=run_dir / ".temp_cache"),
        tracker=tracker,
        client=client,
        mock=mock,
    )

    # Async Pipeline Runner
    async def _execute_pipeline():
        console.print("[bold cyan]1/4 Generating visual intents with Gemini...[/bold cyan]")
        intents = await intent_gen.generate_all_intents(
            segments=target_segments, full_script=raw_script, batch_size=5
        )
        console.print(f"[green]✓ Generated {len(intents)} visual intents[/green]")

        reports: list[SegmentReport] = []
        no_match_segments: list[str] = []

        for idx, (seg, intent) in enumerate(zip(target_segments, intents), start=1):
            console.print(f"[cyan]Processing {seg.id} ({idx}/{len(target_segments)}): searching candidates...[/cyan]")
            candidates, _l1, _l2, _phash = await search_mgr.gather_and_filter_candidates(
                queries=intent.queries,
                image_types=intent.image_types,
                thumbs_dir=thumbs_dir,
                max_candidates=settings.candidates_per_segment,
            )

            console.print(f"[cyan]Evaluating {seg.id} with Gemini Vision & Layer 3 watermark check ({len(candidates)} candidates)...[/cyan]")
            report = await reranker.rerank_and_filter_segment(
                segment=seg,
                intent=intent,
                candidates=candidates,
                full_images_dir=full_images_dir,
            )

            # Optional YouTube search
            if youtube and settings.youtube_api_key:
                console.print(f"[cyan]Fetching YouTube leads for {seg.id}...[/cyan]")
                yt_leads = await search_mgr.search_youtube_leads(
                    query=intent.queries[0] if intent.queries else seg.text,
                    segment_id=seg.id,
                    limit=3,
                )
                report.video_leads = yt_leads

            top_score_str = f"Top score: {report.top_picks[0].relevance_score:.1f}" if report.top_picks else "No top picks"
            console.print(f"[green]✓ {seg.id} completed. Status: {report.status.value.upper()} ({top_score_str})[/green]")

            reports.append(report)
            if report.status.value == "no_match":
                no_match_segments.append(seg.id)

        # 4. Generate Reports
        console.print("[bold cyan]Writing HTML and CSV reports...[/bold cyan]")
        html_path = run_dir / "report.html"
        csv_path = run_dir / "report.csv"
        generate_html_report(
            reports=reports,
            output_html_path=html_path,
            script_name=script_stem,
            tracker=tracker,
        )
        export_reports_to_csv(reports=reports, output_csv_path=csv_path)

        return html_path, csv_path, no_match_segments

    # Run loop
    html_path, csv_path, no_match_segments = asyncio.run(_execute_pipeline())

    # Summary Report Display
    console.print("\n")
    tracker.print_summary(console=console)

    if no_match_segments:
        console.print(
            f"[bold yellow]⚠️ Segments with status NO_MATCH:[/bold yellow] {', '.join(no_match_segments)}"
        )
    else:
        console.print("[bold green]✓ All segments have matching candidates![/bold green]")

    console.print(f"\n[bold green]Report HTML generated:[/bold green] [underline]{html_path}[/underline]")
    console.print(f"[bold green]Report CSV generated:[/bold green]  [underline]{csv_path}[/underline]")


@app.command(name="download-selected")
def download_selected(
    csv_file: Path = typer.Argument(..., help="Path to report.csv or selected CSV file"),
    dest: Path = typer.Option(Path("downloads"), "--dest", "-d", help="Destination folder for DaVinci Resolve media"),
):
    """Download chosen images into folders named by segment ID ready for DaVinci Resolve import."""
    settings = Settings()
    downloader = AssetDownloader(
        user_agent=settings.wikimedia_user_agent,
        download_dir=dest,
        concurrency=settings.concurrent_download_limit,
    )

    console.print(f"[cyan]Downloading assets from [bold]{csv_file}[/bold] into [bold]{dest}[/bold]...[/cyan]")
    try:
        out_dir = asyncio.run(downloader.download_from_csv(csv_file))
        console.print(f"[bold green]✓ Assets downloaded successfully to:[/bold green] [underline]{out_dir}[/underline]")
        console.print(f"[bold green]✓ Consolidated credits saved to:[/bold green] [underline]{out_dir / 'credits.txt'}[/underline]")
    except (OSError, ValueError, RuntimeError) as e:
        console.print(f"[bold red]Download error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="cache-clear")
def cache_clear():
    """Clear Footage Finder local cache."""
    cache = DiskCache()
    count = cache.clear()
    console.print(f"[green]Cleared {count} cached files.[/green]")


@app.command(name="ui")
def start_ui(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host interface to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to run Studio API server on"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
):
    """Launch Footage Finder Studio API backend server."""
    import uvicorn
    console.print(f"[bold green]Starting Footage Finder Studio API at[/bold green] [underline]http://{host}:{port}[/underline]")
    uvicorn.run("footage_finder.server:app", host=host, port=port, reload=reload)


def main():
    app()


if __name__ == "__main__":
    main()
