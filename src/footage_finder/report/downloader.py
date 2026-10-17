"""Downloader for DaVinci Resolve import with credit sidecars."""

from __future__ import annotations

import asyncio
import re
import urllib.parse
from pathlib import Path

import httpx

from footage_finder.report.csv_generator import read_selected_csv


def sanitize_filename_part(text: str) -> str:
    """Sanitize text to safe filesystem characters (alphanumeric, underscore, dash)."""
    clean = re.sub(r"[^\w\-]", "_", text).strip("_")
    return clean[:40] or "asset"


def determine_extension_from_url_or_content_type(url: str, content_type: str | None = None) -> str:
    """Determine proper image extension (.jpg, .png, .webp)."""
    parsed = urllib.parse.urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext in [".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".gif"]:
        return ".jpg" if ext == ".jpeg" else ext

    if content_type:
        ct = content_type.lower()
        if "png" in ct:
            return ".png"
        elif "webp" in ct:
            return ".webp"
        elif "gif" in ct:
            return ".gif"
    return ".jpg"


class AssetDownloader:
    def __init__(
        self,
        user_agent: str = "FootageFinder/1.0",
        download_dir: Path = Path("downloads"),
        concurrency: int = 4,
        timeout: float = 20.0,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.user_agent = user_agent
        self.download_dir = Path(download_dir)
        self.download_sem = asyncio.Semaphore(concurrency)
        self.timeout = timeout
        self.client = http_client

    async def download_asset(
        self,
        row: dict,
        dest_folder: Path,
        index_in_segment: int,
        client: httpx.AsyncClient,
    ) -> tuple[bool, str]:
        """Download one asset with sidecar metadata credit file."""
        seg_id = row.get("segment_id", "S000")
        img_url = row.get("image_url", "").strip()
        domain = sanitize_filename_part(row.get("source_domain", "web"))
        author = row.get("author", "Unknown")
        license_str = row.get("license", "unknown – verify")
        attr_text = row.get("attribution_text", "")
        source_page = row.get("source_page_url", "")

        if not img_url:
            return False, ""

        dest_folder.mkdir(parents=True, exist_ok=True)

        headers = {"User-Agent": self.user_agent}
        try:
            async with self.download_sem:
                resp = await client.get(img_url, headers=headers, follow_redirects=True)
                if resp.status_code != 200:
                    return False, f"HTTP {resp.status_code}"

                ext = determine_extension_from_url_or_content_type(
                    img_url, resp.headers.get("content-type")
                )
                file_stem = f"{seg_id}_{index_in_segment:02d}_{domain}"
                img_path = dest_folder / f"{file_stem}{ext}"
                sidecar_path = dest_folder / f"{file_stem}.credit.txt"

                img_path.write_bytes(resp.content)

                # Write credit sidecar
                sidecar_content = (
                    f"Segment: {seg_id}\n"
                    f"Source URL: {img_url}\n"
                    f"Source Page: {source_page}\n"
                    f"Author: {author}\n"
                    f"License: {license_str}\n"
                    f"Attribution:\n{attr_text or img_url}\n"
                )
                sidecar_path.write_text(sidecar_content, encoding="utf-8")

                credit_line = (
                    f"[{seg_id}] {attr_text or f'{author} ({license_str}) - {source_page or img_url}'}"
                )
                return True, credit_line
        except (httpx.HTTPError, OSError) as e:
            return False, str(e)

    async def download_from_csv(self, csv_path: Path) -> Path:
        """Download all selected images in CSV organized into folders by segment ID."""
        rows = read_selected_csv(csv_path)
        if not rows:
            return self.download_dir

        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Group by segment ID
        segments_map: dict[str, list[dict]] = {}
        for r in rows:
            sid = r.get("segment_id", "S000")
            segments_map.setdefault(sid, []).append(r)

        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        consolidated_credits: list[str] = [
            "===========================================================",
            "FOOTAGE FINDER - ATTRIBUTION & CREDITS (DaVinci Resolve)",
            "Paste necessary lines into your YouTube video description",
            "===========================================================\n",
        ]

        try:
            tasks = []
            for sid, items in segments_map.items():
                # Folder e.g. downloads/S001_Trinity_test
                seg_folder = self.download_dir / sid
                for idx, row in enumerate(items, start=1):
                    tasks.append(self.download_asset(row, seg_folder, idx, client))

            results = await asyncio.gather(*tasks)
            for ok, credit_line in results:
                if ok and credit_line:
                    consolidated_credits.append(credit_line)

            # Write master credits.txt
            master_credits_path = self.download_dir / "credits.txt"
            master_credits_path.write_text("\n".join(consolidated_credits) + "\n", encoding="utf-8")
        finally:
            if not self.client:
                await client.aclose()

        return self.download_dir
