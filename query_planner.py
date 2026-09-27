from google import genai
from google.genai import types

from llm_json import parse_json

MODEL = "gemini-2.5-flash"


class QueryPlanner:
    """Turns broad (industry, category, country) inputs into concrete, platform-agnostic
    search terms plus platform-specific community hints (subreddits, channels, ...)."""

    def __init__(self, client: genai.Client):
        self.client = client

    def plan(self, industry: str, category: str, country: str, platform: str, num_search_terms: int = 10) -> dict:
        neutral_count = round(num_search_terms * 0.5)
        positive_count = round(num_search_terms * 0.25)
        negative_count = max(num_search_terms - neutral_count - positive_count, 0)

        # community_hints (subreddits to search within) are only a Reddit concept — YouTube
        # has no equivalent scoping mechanism, so asking for them there just produces unused,
        # often low-quality handle-style strings. search_terms alone (exactly
        # num_search_terms of them) are what YouTube actually searches.
        hints_block = ""
        if platform == "reddit":
            hints_block = f"""

Also produce 5-10 community hints likely to contain relevant discussions: subreddit names \
(no "r/" prefix). Include both general ones and ones specific to {country} or this niche if \
you know of any real, existing subreddits. Do not invent names you're not confident are real \
— it's fine to return fewer than 10."""

        prompt = f"""A researcher wants to discover real, unprompted problems that users based \
in {country} have with the following — by searching {platform} for relevant content and then \
reading the comments/discussion on it:

Industry: {industry}
Category: {category}

CRITICAL — avoid selection bias: if you only generate complaint-shaped searches like \
"{category} problems" or "{category} scam", you will mostly find comments that were already \
primed by that framing — a self-fulfilling result that makes those specific problems look \
more common than they really are, and misses problems nobody thought to search for directly. \
The strongest, most organic signal of a real problem is a complaint that shows up as an aside \
in the comments on completely neutral content — e.g. someone commenting "my child won't do \
any activity without asking for the phone" on a plain toddler-routine video is far more \
trustworthy evidence of a screen-time problem than a comment found by searching "toddler \
screen addiction", because the search itself didn't put that idea in anyone's head.

So: search for the CONTEXT in which problems naturally occur, not just the problems \
themselves. Produce exactly {num_search_terms} search phrases, split into three kinds:

1. NEUTRAL ({neutral_count} phrases) — everyday, purely informational phrases about this \
topic with zero problem or sentiment framing: daily routines, "how to", comparisons, vlogs, \
"day in the life", general how-people-do-this content. This should be the largest group.
2. POSITIVE ({positive_count} phrases) — review/best-of/satisfaction-seeking phrasing that \
still draws organic, unprimed comments: "best X", "X review", "is X worth it", "why I switched \
to X".
3. NEGATIVE ({negative_count} phrases) — explicit venting/complaint phrasing, in the plain \
informal language real users would type: "why is X so confusing", "X ripped me off", "X waste \
of money". Still useful, but must not dominate the list.{hints_block}

Return a JSON object: {{"search_terms": ["..."], "community_hints": ["..."]}}"""

        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        data = parse_json(response.text)
        data.setdefault("search_terms", [])
        data.setdefault("community_hints", [])
        return data
