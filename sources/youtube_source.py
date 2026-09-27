import os
import re
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models import RawItem
from sources.base import Source

_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
_SHORT_MAX_SECONDS = 60  # YouTube Shorts' classic length cap; used as the Short/Video heuristic


class YouTubeSource(Source):
    name = "youtube"

    def __init__(self, api_key: str):
        self.youtube = build("youtube", "v3", developerKey=api_key)

    @classmethod
    def from_env(cls) -> "YouTubeSource":
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing YOUTUBE_API_KEY. In Google Cloud Console: create/select a "
                "project, enable the 'YouTube Data API v3', then create an API key "
                "under Credentials, and set YOUTUBE_API_KEY in your .env file."
            )
        return cls(api_key)

    def fetch(
        self,
        search_terms: list[str],
        community_hints: list[str],
        limit: int = 200,
        items_per_query: int | None = None,
        comments_per_item: int | None = None,
        exclude_shorts: bool = True,
        min_views: int = 0,
    ) -> list[RawItem]:
        items: list[RawItem] = []
        seen_video_ids: set[str] = set()
        seen_comment_ids: set[str] = set()

        # community_hints is unused here — YouTube has no subreddit-like scoping concept,
        # and merging it into the query list made the total exceed num_search_terms and
        # let low-quality handle-style strings slip in as literal searches. search_terms
        # alone (exactly num_search_terms of them) are what gets searched.
        queries = list(dict.fromkeys(search_terms))
        if not queries:
            return items

        videos_per_query = items_per_query or 5
        comments_per_video = comments_per_item or 8

        # Phase 1: collect video candidates across all queries. When excluding Shorts, we
        # ask YouTube's search API itself to skip sub-4-minute videos (videoDuration
        # "medium"/"long") — Shorts (<=60s) are a subset of that, so they're never
        # returned as candidates at all, rather than being fetched and filtered afterward.
        candidates: list[tuple[str, dict, str]] = []  # (video_id, snippet, search_term)
        for query in queries:
            for search_item in self._search_videos(query, videos_per_query, exclude_shorts):
                video_id = search_item.get("id", {}).get("videoId")
                if not video_id or video_id in seen_video_ids:
                    continue
                seen_video_ids.add(video_id)
                candidates.append((video_id, search_item["snippet"], query))

        if not candidates:
            return items

        # Phase 2: batch-fetch duration (for Short/Video labeling) + view count (cheap:
        # ~1 unit per 50 videos) for every candidate.
        metadata = self._fetch_video_metadata([video_id for video_id, _, _ in candidates])

        if min_views > 0:
            before = len(candidates)
            candidates = [c for c in candidates if metadata.get(c[0], {}).get("view_count", 0) >= min_views]
            skipped = before - len(candidates)
            if skipped:
                print(f"  [info] excluded {skipped} video(s) below {min_views} views")

        # Phase 3: build video items + fetch their comments.
        for video_id, snippet, search_term in candidates:
            if len(items) >= limit:
                break
            meta = metadata.get(video_id, {"media_type": "Video", "view_count": 0})
            video_title = snippet.get("title", "")
            self._add_video(video_id, snippet, items, search_term, meta)
            self._add_comments(
                video_id,
                snippet.get("channelTitle", ""),
                comments_per_video,
                items,
                seen_comment_ids,
                limit,
                search_term,
                video_title,
                meta,
            )

        return items

    def _search_videos(self, query: str, videos_per_query: int, exclude_shorts: bool) -> list[dict]:
        """Search YouTube for `query`, returning up to `videos_per_query` search-result
        items. When exclude_shorts, queries the "medium" (4-20min) and "long" (>20min)
        duration buckets instead of "any" — Shorts (<=60s) fall in the excluded "short"
        (<4min) bucket, so they're never returned in the first place."""
        if not exclude_shorts:
            return self._search_once(query, videos_per_query, "any")

        results: list[dict] = []
        for duration in ("medium", "long"):
            results.extend(self._search_once(query, videos_per_query, duration))
        return results[:videos_per_query]

    def _search_once(self, query: str, max_results: int, video_duration: str) -> list[dict]:
        try:
            resp = (
                self.youtube.search()
                .list(
                    q=query,
                    part="snippet",
                    type="video",
                    maxResults=max_results,
                    order="relevance",
                    videoDuration=video_duration,
                )
                .execute()
            )
            return resp.get("items", [])
        except HttpError as exc:
            print(f"  [warn] YouTube search failed for '{query}' ({video_duration}): {exc}")
            return []

    def _fetch_video_metadata(self, video_ids: list[str]) -> dict[str, dict]:
        """Returns {video_id: {"media_type": "Short"|"Video", "view_count": int}}."""
        metadata: dict[str, dict] = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            try:
                resp = (
                    self.youtube.videos()
                    .list(part="contentDetails,statistics", id=",".join(batch))
                    .execute()
                )
            except HttpError as exc:
                print(f"  [warn] couldn't fetch video metadata (duration/views): {exc}")
                continue
            for v in resp.get("items", []):
                seconds = _parse_iso8601_duration(v.get("contentDetails", {}).get("duration", ""))
                view_count = int(v.get("statistics", {}).get("viewCount", 0))
                metadata[v["id"]] = {
                    "media_type": "Short" if seconds and seconds <= _SHORT_MAX_SECONDS else "Video",
                    "view_count": view_count,
                }
        return metadata

    def _add_video(
        self, video_id: str, snippet: dict, items: list[RawItem], search_term: str, meta: dict
    ) -> None:
        text = f"{snippet.get('title', '')}\n{snippet.get('description', '')}".strip()
        if not text:
            return
        items.append(
            RawItem(
                id=video_id,
                platform=self.name,
                text=text,
                url=f"https://www.youtube.com/watch?v={video_id}",
                author=snippet.get("channelTitle"),
                created_utc=_parse_dt(snippet.get("publishedAt")),
                score=0,
                source_context=snippet.get("channelTitle", ""),
                search_term=search_term,
                parent_title=snippet.get("title", ""),
                item_type="post",
                media_type=meta["media_type"],
                view_count=meta["view_count"],
            )
        )

    def _add_comments(
        self,
        video_id: str,
        channel_title: str,
        max_comments: int,
        items: list[RawItem],
        seen_ids: set[str],
        limit: int,
        search_term: str,
        video_title: str,
        meta: dict,
    ) -> None:
        try:
            resp = (
                self.youtube.commentThreads()
                .list(part="snippet", videoId=video_id, maxResults=max_comments, order="relevance", textFormat="plainText")
                .execute()
            )
        except HttpError as exc:
            print(f"  [warn] couldn't load comments for {video_id}: {getattr(exc, 'reason', exc)}")
            return

        for comment_item in resp.get("items", []):
            if len(items) >= limit:
                return
            comment_id = comment_item["id"]
            if comment_id in seen_ids:
                continue
            seen_ids.add(comment_id)
            top = comment_item["snippet"]["topLevelComment"]["snippet"]
            text = (top.get("textDisplay") or "").strip()
            if not text:
                continue
            items.append(
                RawItem(
                    id=comment_id,
                    platform=self.name,
                    text=text,
                    url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
                    author=top.get("authorDisplayName"),
                    created_utc=_parse_dt(top.get("publishedAt")),
                    score=top.get("likeCount", 0),
                    source_context=channel_title,
                    search_term=search_term,
                    parent_title=video_title,
                    item_type="comment",
                    media_type=meta["media_type"],
                    view_count=meta["view_count"],
                )
            )


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_iso8601_duration(duration: str) -> int:
    match = _DURATION_RE.match(duration or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds
