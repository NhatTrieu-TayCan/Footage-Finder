"""Usage and cost estimation tracker."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

from footage_finder.config import load_pricing
from footage_finder.models import UsageStats


class CostTracker:
    def __init__(self, pricing_dict: dict[str, Any] | None = None):
        self.pricing = pricing_dict if pricing_dict is not None else load_pricing()
        self.stats = UsageStats()
        self.text_model_name: str = "gemini-2.5-flash"
        self.vision_model_name: str = "gemini-2.5-flash"

    def record_gemini_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        is_vision: bool = False,
    ) -> None:
        if is_vision:
            self.stats.gemini_vision_calls += 1
            self.vision_model_name = model
        else:
            self.stats.gemini_text_calls += 1
            self.text_model_name = model

        self.stats.input_tokens += input_tokens
        self.stats.output_tokens += output_tokens
        self.stats.cached_tokens += cached_tokens
        self._update_cost()

    def record_search_query(self, provider: str, count: int = 1) -> None:
        p = provider.lower()
        if "serper" in p:
            self.stats.serper_queries += count
        elif "wikimedia" in p:
            self.stats.wikimedia_queries += count
        elif "youtube" in p:
            self.stats.youtube_queries += count
        self._update_cost()

    def record_watermark_removal(self, layer: int, count: int = 1) -> None:
        if layer == 1:
            self.stats.watermark_removed_layer1 += count
        elif layer == 2:
            self.stats.watermark_removed_layer2 += count
        elif layer == 3:
            self.stats.watermark_removed_layer3 += count

    def _update_cost(self) -> None:
        cost = 0.0
        gemini_pricing = self.pricing.get("gemini", {})
        # Find matching model key
        model_key = self.text_model_name.replace("models/", "").lower()
        price_cfg = gemini_pricing.get(
            model_key, gemini_pricing.get("gemini-2.5-flash", {})
        )

        in_rate = price_cfg.get("input_token_per_million", 0.15) / 1_000_000.0
        out_rate = price_cfg.get("output_token_per_million", 0.60) / 1_000_000.0
        cached_rate = (
            price_cfg.get("cached_input_token_per_million", 0.0375) / 1_000_000.0
        )

        non_cached_in = max(0, self.stats.input_tokens - self.stats.cached_tokens)
        cost += non_cached_in * in_rate
        cost += self.stats.cached_tokens * cached_rate
        cost += self.stats.output_tokens * out_rate

        # Serper
        serper_cfg = self.pricing.get("serper", {})
        serper_rate = serper_cfg.get("cost_per_thousand_queries", 1.00) / 1000.0
        cost += self.stats.serper_queries * serper_rate

        self.stats.estimated_cost_usd = round(cost, 5)

    def get_summary(self) -> UsageStats:
        self._update_cost()
        return self.stats

    def print_summary(self, console: Console | None = None) -> None:
        c = console or Console()
        self._update_cost()

        table = Table(
            title="Footage Finder Execution Summary & Estimated Cost", show_header=True
        )
        table.add_column("Category", style="cyan")
        table.add_column("Count / Details", style="green")
        table.add_column("Estimated Cost (USD)", style="yellow")

        gemini_summary = (
            f"Calls: {self.stats.gemini_text_calls} text, {self.stats.gemini_vision_calls} vision\n"
            f"Tokens: {self.stats.input_tokens:,} in, {self.stats.output_tokens:,} out"
        )
        table.add_row(
            "Gemini API", gemini_summary, f"${self.stats.estimated_cost_usd:.4f} (est.)"
        )

        serper_cost = (
            self.pricing.get("serper", {}).get("cost_per_thousand_queries", 1.0)
            / 1000.0
        ) * self.stats.serper_queries
        table.add_row(
            "Serper.dev Search",
            f"{self.stats.serper_queries} queries",
            f"${serper_cost:.4f}",
        )
        table.add_row(
            "Wikimedia Commons",
            f"{self.stats.wikimedia_queries} queries",
            "$0.0000 (Free)",
        )
        if self.stats.youtube_queries > 0:
            table.add_row(
                "YouTube Data API",
                f"{self.stats.youtube_queries} queries",
                "$0.0000 (Quota tier)",
            )

        # Watermark defense breakdown
        total_wm = (
            self.stats.watermark_removed_layer1
            + self.stats.watermark_removed_layer2
            + self.stats.watermark_removed_layer3
        )
        wm_details = (
            f"Total removed: {total_wm}\n"
            f"• Layer 1 (Domain Blocklist): {self.stats.watermark_removed_layer1}\n"
            f"• Layer 2 (URL Heuristics): {self.stats.watermark_removed_layer2}\n"
            f"• Layer 3 (Full-Image Vision): {self.stats.watermark_removed_layer3}"
        )
        table.add_row("Watermark Defenses", wm_details, "Blocked")

        c.print(table)
