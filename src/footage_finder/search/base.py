"""Base search provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from footage_finder.models import ImageCandidate


class BaseSearchProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'serper', 'wikimedia')."""

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[ImageCandidate]:
        """Execute image search and return normalized ImageCandidate instances."""
