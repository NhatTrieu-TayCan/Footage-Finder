"""Search providers package."""

from footage_finder.search.base import BaseSearchProvider
from footage_finder.search.manager import SearchManager
from footage_finder.search.serper import SerperProvider
from footage_finder.search.wikimedia import WikimediaProvider
from footage_finder.search.youtube import YouTubeProvider

__all__ = [
    "BaseSearchProvider",
    "SearchManager",
    "SerperProvider",
    "WikimediaProvider",
    "YouTubeProvider",
]
