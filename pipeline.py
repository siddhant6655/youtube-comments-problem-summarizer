import os
from typing import Callable

from google import genai

from bucketing.extractor import ProblemBucketer
from query_planner import QueryPlanner
from sources.registry import get_source

# Not user-facing — just a sanity ceiling so a bug (or an extreme items_per_query /
# comments_per_item combo) can't fetch forever. The real controls are items_per_query
# and comments_per_item.
_SAFETY_MAX_ITEMS = 5000


def run(
    industry: str,
    category: str,
    country: str,
    platform: str = "reddit",
    num_search_terms: int = 10,
    items_per_query: int = 5,
    comments_per_item: int = 8,
    exclude_shorts: bool = True,
    min_views: int = 0,
    log: Callable[[str], None] = print,
) -> dict:
    """num_search_terms controls how many search phrases the planner generates.
    items_per_query / comments_per_item are the platform-agnostic tuning knobs: for
    YouTube, videos fetched per search term / comments fetched per video; for Reddit,
    submissions fetched per subreddit search / comments fetched per submission."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY. Set it in your .env file.")
    client = genai.Client(api_key=api_key)

    log("[plan] generating search terms...")
    planner = QueryPlanner(client)
    plan = planner.plan(industry, category, country, platform, num_search_terms)
    log(f"[plan] search terms: {plan['search_terms']}")
    log(f"[plan] community hints: {plan['community_hints']}")

    log(f"[fetch] searching {platform}...")
    source = get_source(platform)
    items = source.fetch(
        plan["search_terms"],
        plan["community_hints"],
        limit=_SAFETY_MAX_ITEMS,
        items_per_query=items_per_query,
        comments_per_item=comments_per_item,
        exclude_shorts=exclude_shorts,
        min_views=min_views,
    )
    log(f"[fetch] collected {len(items)} raw items from {platform}")

    log("[extract] analyzing raw items for stated problems...")
    bucketer = ProblemBucketer(client)
    problems = bucketer.extract_problems(items)
    log(f"[extract] found {len(problems)} explicit problem statements")

    log("[bucket] clustering problems into themes...")
    buckets = bucketer.bucket_problems(problems)
    log(f"[bucket] grouped into {len(buckets)} buckets")

    return {
        "industry": industry,
        "category": category,
        "country": country,
        "platform": platform,
        "raw_item_count": len(items),
        "problem_count": len(problems),
        "buckets": buckets,
        "raw_items": items,
        "problems": problems,
    }
