# Project Non-Negotiable Rules (Footage Finder)

- **NO WATERMARKED IMAGES in top picks or alternates**: Watermark filtering is a hard filter, never just a score penalty.
- **Licensing honesty**: Never claim an image is free to use unless the source metadata specifically states it (e.g. Wikimedia extmetadata). Otherwise mark license as "unknown – verify".
- **No direct Google scraping**: Never scrape Google HTML. Only use official/structured APIs (Serper.dev, Wikimedia Commons, YouTube Data API v3).
- **External call resilience**: Every external call must implement timeouts, retries with exponential backoff on 429/5xx, and concurrency limits via semaphores.
- **Config-driven**: No hardcoded prices or model names in code; everything in config (`.env` and `config/pricing.toml`).
- **Domain & URL blocklist defense**:
  - Layer 1: Domain blocklist (`config/blocklist.txt`) drops candidates before Gemini calls.
  - Layer 2: URL regex/heuristics drop stock preview/watermark patterns.
  - Layer 3: Dedicated Gemini vision check on full-size image (not just thumbnail) for any candidate reaching top picks or alternates. Watermarked or stock previews are completely purged and the next-best candidate is promoted.
- **Testing & verification**: Pytest suite with mock fixtures; `--mock` flag runs zero-API-cost pipeline; interactive report verified in browser.
