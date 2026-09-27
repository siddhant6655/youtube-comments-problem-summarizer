from google import genai
from google.genai import types

from llm_json import parse_json
from models import Bucket, ProblemStatement, RawItem

MODEL = "gemini-2.5-flash"


class ProblemBucketer:
    """Extracts explicit problem statements from raw platform content, then clusters
    them into labeled thematic buckets. Platform-agnostic — works on RawItems from any
    Source."""

    def __init__(self, client: genai.Client):
        self.client = client

    def extract_problems(self, items: list[RawItem], batch_size: int = 20) -> list[ProblemStatement]:
        problems: list[ProblemStatement] = []
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            problems.extend(self._extract_batch(batch))
        return problems

    def _extract_batch(self, batch: list[RawItem]) -> list[ProblemStatement]:
        numbered = "\n\n".join(f"[{idx}] {item.text[:800]}" for idx, item in enumerate(batch))
        prompt = f"""Below are numbered posts/comments from an online platform. For each one, \
identify any concrete problem, pain point, or complaint the author explicitly states — in \
their own words, not generic marketing language. Skip items with no real stated problem \
(jokes, pure praise, unrelated chatter). A single item may yield zero, one, or multiple \
problems.

Return a JSON array of objects like \
{{"item_index": <int>, "problem": "<concise one-sentence restatement of the problem>"}}.

Items:
{numbered}"""

        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        try:
            data = parse_json(response.text)
        except (ValueError, KeyError):
            return []

        results = []
        for entry in data:
            idx = entry.get("item_index")
            problem_text = entry.get("problem")
            if idx is None or problem_text is None or not (0 <= idx < len(batch)):
                continue
            item = batch[idx]
            results.append(
                ProblemStatement(
                    text=problem_text,
                    raw_item_id=item.id,
                    url=item.url,
                    platform=item.platform,
                    context=item.source_context,
                    search_term=item.search_term,
                )
            )
        return results

    def bucket_problems(self, problems: list[ProblemStatement], max_buckets: int = 12) -> list[Bucket]:
        if not problems:
            return []

        numbered = "\n".join(f"[{idx}] {p.text}" for idx, p in enumerate(problems))
        prompt = f"""Group the following user-stated problems into at most {max_buckets} clear, \
distinct thematic buckets. Every problem must belong to exactly one bucket. Use buckets \
that would be useful to a product/business person scanning for recurring pain points — \
not overly granular, not a single catch-all.

Return a JSON array of objects like \
{{"label": "<short bucket name, 2-5 words>", "description": "<one sentence summarizing \
the bucket>", "item_indices": [<ints>]}}. Order the array by number of items, descending.

Problems:
{numbered}"""

        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        data = parse_json(response.text)

        buckets = []
        for entry in data:
            indices = [i for i in entry.get("item_indices", []) if 0 <= i < len(problems)]
            if not indices:
                continue
            members = [problems[i] for i in indices]
            label = entry.get("label", "Untitled")
            seen_urls: list[str] = []
            for m in members:
                m.bucket_label = label  # mutates the shared ProblemStatement objects
                if m.url not in seen_urls:
                    seen_urls.append(m.url)
            buckets.append(
                Bucket(
                    label=label,
                    description=entry.get("description", ""),
                    count=len(members),
                    example_quotes=[m.text for m in members[:5]],
                    example_urls=seen_urls[:5],
                )
            )
        buckets.sort(key=lambda b: b.count, reverse=True)
        return buckets
