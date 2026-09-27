import os
from datetime import datetime, timezone

import praw

from models import RawItem
from sources.base import Source


class RedditSource(Source):
    name = "reddit"

    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        self.reddit.read_only = True

    @classmethod
    def from_env(cls) -> "RedditSource":
        client_id = os.environ.get("REDDIT_CLIENT_ID")
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
        user_agent = os.environ.get("REDDIT_USER_AGENT", "problem-scraper/0.1")
        if not client_id or not client_secret:
            raise RuntimeError(
                "Missing REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET. "
                "Register a free 'script' app at https://www.reddit.com/prefs/apps "
                "and set them (plus REDDIT_USER_AGENT) in your .env file."
            )
        return cls(client_id, client_secret, user_agent)

    def fetch(
        self,
        search_terms: list[str],
        community_hints: list[str],
        limit: int = 200,
        items_per_query: int | None = None,
        comments_per_item: int | None = None,
        exclude_shorts: bool = True,  # not applicable on Reddit; accepted for interface consistency
        min_views: int = 0,  # not applicable on Reddit; accepted for interface consistency
    ) -> list[RawItem]:
        items: list[RawItem] = []
        seen_ids: set[str] = set()

        subreddits_to_search = community_hints or ["all"]
        per_query_limit = items_per_query or max(10, limit // max(len(search_terms) * len(subreddits_to_search), 1))
        comments_per_submission = comments_per_item or 5

        for term in search_terms:
            for sub_name in subreddits_to_search:
                if len(items) >= limit:
                    return items
                try:
                    subreddit = self.reddit.subreddit(sub_name)
                    for submission in subreddit.search(term, sort="relevance", time_filter="year", limit=per_query_limit):
                        if len(items) >= limit:
                            return items
                        self._add_submission(submission, items, seen_ids, comments_per_submission, term)
                except Exception as exc:
                    print(f"  [warn] skipping r/{sub_name} search for '{term}': {exc}")
                    continue

        return items

    def _add_submission(
        self,
        submission,
        items: list[RawItem],
        seen_ids: set[str],
        comments_per_submission: int = 5,
        search_term: str = "",
    ) -> None:
        if submission.id not in seen_ids:
            seen_ids.add(submission.id)
            text = f"{submission.title}\n{submission.selftext or ''}".strip()
            if text:
                items.append(
                    RawItem(
                        id=submission.id,
                        platform=self.name,
                        text=text,
                        url=f"https://reddit.com{submission.permalink}",
                        author=str(submission.author) if submission.author else None,
                        created_utc=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
                        score=submission.score,
                        source_context=f"r/{submission.subreddit.display_name}",
                        search_term=search_term,
                        parent_title=submission.title,
                        item_type="post",
                    )
                )

        try:
            submission.comments.replace_more(limit=0)
            for comment in submission.comments[:comments_per_submission]:
                if comment.id in seen_ids or not getattr(comment, "body", None):
                    continue
                seen_ids.add(comment.id)
                items.append(
                    RawItem(
                        id=comment.id,
                        platform=self.name,
                        text=comment.body,
                        url=f"https://reddit.com{comment.permalink}",
                        author=str(comment.author) if comment.author else None,
                        created_utc=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
                        score=comment.score,
                        source_context=f"r/{submission.subreddit.display_name}",
                        search_term=search_term,
                        parent_title=submission.title,
                        item_type="comment",
                    )
                )
        except Exception as exc:
            print(f"  [warn] couldn't load comments for {submission.id}: {exc}")
