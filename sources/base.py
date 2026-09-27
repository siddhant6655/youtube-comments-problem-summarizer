from abc import ABC, abstractmethod
from typing import Optional

from models import RawItem


class Source(ABC):
    """A platform we can pull user-stated content from (Reddit today; YouTube, forums, etc. later).

    To add a new platform: subclass this, implement from_env() and fetch(), then
    register the subclass in sources/registry.py. Nothing else in the pipeline changes.
    """

    name: str

    @classmethod
    @abstractmethod
    def from_env(cls) -> "Source":
        """Construct the source using credentials/config from environment variables."""

    @abstractmethod
    def fetch(
        self,
        search_terms: list[str],
        community_hints: list[str],
        limit: int,
        items_per_query: Optional[int] = None,
        comments_per_item: Optional[int] = None,
        exclude_shorts: bool = True,
        min_views: int = 0,
    ) -> list[RawItem]:
        """Fetch up to `limit` RawItems matching the given search terms.

        community_hints are platform-specific groupings to prioritize (subreddits for
        Reddit, channel/topic names for YouTube, etc.) — implementations may ignore hints
        that don't apply and fall back to a general search.

        items_per_query / comments_per_item are generic tuning knobs (e.g. videos per
        search term / comments per video on YouTube, submissions per subreddit search /
        comments per submission on Reddit). None means "pick a sensible default".

        exclude_shorts and min_views only apply where the concept exists (YouTube); other
        sources ignore them.
        """
