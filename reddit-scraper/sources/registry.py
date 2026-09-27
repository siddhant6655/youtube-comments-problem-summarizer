from sources.base import Source
from sources.reddit_source import RedditSource
from sources.youtube_source import YouTubeSource

# "reddit" needs Reddit-approved OAuth access under their Responsible Builder Policy —
# self-serve app registration is closed as of late 2025. The Source is fully built and
# will work unchanged once you have approved credentials in .env.
SOURCES: dict[str, type[Source]] = {
    "reddit": RedditSource,
    "youtube": YouTubeSource,
}


def get_source(platform: str) -> Source:
    if platform not in SOURCES:
        raise ValueError(f"Unknown platform '{platform}'. Available: {list(SOURCES)}")
    return SOURCES[platform].from_env()
