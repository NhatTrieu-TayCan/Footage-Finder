# Footage Finder 🎬🔍

> **Script-to-Image Footage Research Engine for Faceless Video Creators & Documentary Editors**  
> Designed for DaVinci Resolve workflows across History, Finance, and Tech niches.

Footage Finder transforms raw voiceover narration scripts (`.txt` or `.docx`) into curated, verified, high-resolution visual research reports. It utilizes Google AI Studio's Gemini models for visual intent extraction and multimodal vision ranking, queries structured search APIs (Serper.dev, Wikimedia Commons, and YouTube Data API v3), applies a **strict 3-layer watermark defense**, and downloads chosen assets directly into organized segment bins with attribution sidecars.

---

## ⚡ Key Highlights

- **3-Layer Watermark Defense (Hard Filter):** Watermarked images and stock preview comps are dropped unconditionally—never merely penalized.
  1. *Layer 1 (Domain Blocklist):* Drops aggregator and stock domains before vision evaluation (`config/blocklist.txt`).
  2. *Layer 2 (URL Heuristics):* Drops preview/watermark URL patterns (`wm_`, `/comp/`, `preview`).
  3. *Layer 3 (Full-Image Vision Check):* Downloads the full asset (up to 8 MB) and inspects it with Gemini Vision (`has_watermark`, `is_stock_preview`). Watermarked assets are rejected and alternates promoted.
- **DaVinci Resolve Ready:** Downloader creates folders partitioned by segment (`S001`, `S002`, ...) with standardized names (`S001_01_commons_wikimedia_org.jpg`), individual `.credit.txt` sidecars, and a consolidated `credits.txt` ready to paste into YouTube video descriptions.
- **Interactive Dark-Mode HTML Report:** Complete with local image caching, responsive score badges, filter toggles, checkboxes, and client-side selected CSV export.
- **Safe & Official:** Zero Google HTML scraping; resilient async networking with exponential backoff and rate-limiting semaphores.

---

## 🚀 Quickstart & Setup with `uv`

This project is built using Python 3.11+ and managed strictly with [`uv`](https://github.com/astral-sh/uv).

### 1. Install `uv`
If you do not have `uv` installed:
```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via Homebrew (macOS)
brew install uv
```

### 2. Clone and Install Dependencies
```bash
git clone https://github.com/nhattrieu/Footage-Finder.git
cd Footage-Finder

# Sync virtualenv and install all dependencies
uv sync
```

### 3. Configure API Keys
Copy the example environment file:
```bash
cp .env.example .env
```
Open `.env` and fill in your keys:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
SERPER_API_KEY=your_serper_api_key_here          # Optional for web image search
YOUTUBE_API_KEY=your_youtube_api_key_here        # Optional for video leads (--youtube)

GEMINI_TEXT_MODEL=gemini-3.8-flash
GEMINI_VISION_MODEL=gemini-3.8-flash
WIKIMEDIA_USER_AGENT=FootageFinder/1.0 (https://github.com/yourname/Footage-Finder; contact@footagefinder.app)
```

---

## 🔑 Obtaining API Keys

### 1. Google Gemini API (`GEMINI_API_KEY`)
1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Click **Get API key** and create a project key.
3. Paste it into `.env` as `GEMINI_API_KEY`.
*(Footage Finder uses the official `google-genai` SDK and validates available models at startup).*

### 2. Serper.dev Image Search (`SERPER_API_KEY`)
1. Sign up at [Serper.dev](https://serper.dev/).
2. Grab your API key from the dashboard (free tier includes 2,500 free queries).
3. Paste it into `.env` as `SERPER_API_KEY`.

### 3. YouTube Data API v3 (`YOUTUBE_API_KEY`)
1. Visit the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable **YouTube Data API v3**.
3. Create an API Key in **Credentials** and add it to `.env` as `YOUTUBE_API_KEY`.
*(Video leads are disabled by default; enable via `--youtube`).*

---

## 🛡️ Editing the Watermark Blocklist

The domain blocklist is stored in plain text:
```
config/blocklist.txt
```
To add or modify blocked stock/aggregator domains:
1. Open `config/blocklist.txt`.
2. Add the root domain (e.g., `depositphotos.com`, `stock.adobe.com`, `shutterstock.com`) on a new line. Empty lines and lines starting with `#` are ignored.
3. Footage Finder automatically checks candidates and their source pages against this blocklist before querying Gemini Vision.

---

## 🎨 Footage Finder Web Studio UI

Footage Finder includes a **full React + Vite Studio Web Application** featuring:
- **Interactive DaVinci Timeline Scrubber:** Click beats to scrub across your narration script.
- **Real-Time Live SSE Progress Stream:** Watch visual intent extraction, query searches, and Gemini Vision rankings live.
- **Interactive Candidate Boards:** Rank badges, score gauges, license pills, and selection checkboxes.
- **Full-Resolution Inspector & 3-Layer Watermark Audit:** Inspect full image details and review the verification breakdown for Layers 1, 2, and 3.
- **DaVinci Resolve Export Hub:** One-click download of selected assets into `downloads/` bins with credit sidecars + 1-click clipboard copy for YouTube video description credits.

### Launching the Web Studio

```bash
# 1. Launch the Studio UI server (single command)
uv run footage-finder ui

# 2. Open in your browser:
# http://localhost:8000
```

> **For Frontend Development (Vite HMR):**
> ```bash
> # Terminal 1: Backend API
> uv run footage-finder ui
>
> # Terminal 2: Vite React Dev Server
> npm run dev
> # Open http://localhost:5173
> ```

---

## 💻 CLI Commands & Usage

All commands can also be run directly from your terminal:

### 1. Run Pipeline on Narration Script
Analyze a script, search candidates, filter watermarks, and generate reports:
```bash
uv run footage-finder run samples/sample_script.txt
```

#### CLI Flags:
- `--mock`: Run the entire pipeline on mocked offline fixtures (zero external API calls).
- `--resume` / `-r`: Re-use previously cached visual intents and search results on disk.
- `--segments S001-S005`: Restrict processing to a specific segment range.
- `--youtube`: Enable YouTube video lead discovery (disabled by default; leads labeled as "copyrighted – verify before use").
- `--output-dir <path>`: Specify custom report destination.

### 2. Download Selected Assets for DaVinci Resolve
Once you review the report (or use the exported CSV from the browser):
```bash
uv run footage-finder download-selected output/sample_script_20261011_214748/report.csv -d downloads/manhattan_project
```
This produces:
```
downloads/manhattan_project/
├── S003/
│   ├── S003_01_commons_wikimedia_org.jpg
│   ├── S003_01_commons_wikimedia_org.credit.txt
│   ├── S003_02_commons_wikimedia_org.jpg
│   └── S003_02_commons_wikimedia_org.credit.txt
├── S005/
│   ├── S005_01_commons_wikimedia_org.tif
│   └── S005_01_commons_wikimedia_org.credit.txt
└── credits.txt
```

### 3. Clear Cache
```bash
uv run footage-finder cache-clear
```

---

## 🎞️ DaVinci Resolve Import Workflow

1. **Open DaVinci Resolve** to your project timeline.
2. In the **Media Pool**, right-click and choose **New Bin**. Name it after your script (e.g., `Manhattan_Project_Footage`).
3. Drag and drop the downloaded segment folders (`S001`, `S002`, `S003`...) from Finder into your new bin. DaVinci automatically retains the bin hierarchy.
4. **Timeline Editing:**
   - Map `S001` bin assets to your first narration marker/beat.
   - Files are pre-sorted by rank (`S003_01_...` is Top Pick #1).
5. **YouTube Upload & Attribution:**
   - Open `downloads/.../credits.txt`.
   - Copy and paste the consolidated credit text into your YouTube video description to comply with Creative Commons and Public Domain attribution best practices.

---

## 🧪 Testing & Verification

Footage Finder includes automated unit tests with mocked HTTP network layers (`respx`):
```bash
# Run pytest test suite
uv run pytest

# Run Ruff linter
uv run ruff check
```
