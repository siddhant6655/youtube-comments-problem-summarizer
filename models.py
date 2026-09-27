from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RawItem:
    """One piece of user-generated content pulled from a platform (a post, a comment, a video transcript chunk, ...)."""

    id: str
    platform: str
    text: str
    url: str
    author: Optional[str]
    created_utc: datetime
    score: int
    source_context: str  # e.g. "r/personalfinance", a channel name, etc.
    search_term: str = ""  # the planned search phrase that surfaced this item
    parent_title: str = ""  # video title (YouTube) / submission title (Reddit) — same on a post and its comments
    item_type: str = "post"  # "post" (video/submission) or "comment"
    media_type: str = ""  # "Short" or "Video" on YouTube; "" where not applicable
    view_count: int = 0  # the parent video's view count on YouTube; 0 where not applicable


@dataclass
class ProblemStatement:
    """A single problem/pain point extracted from a RawItem, restated concisely."""

    text: str
    raw_item_id: str
    url: str
    platform: str
    context: str
    search_term: str = ""
    bucket_label: str = ""  # filled in by ProblemBucketer.bucket_problems()


@dataclass
class Bucket:
    """A thematic cluster of ProblemStatements."""

    label: str
    description: str
    count: int
    example_quotes: list = field(default_factory=list)
    example_urls: list = field(default_factory=list)
