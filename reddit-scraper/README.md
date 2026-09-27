# problem-scraper

Finds problems/pain points real users state online about a given industry + category +
country, and buckets them into themes — so you can see what people actually complain
about, at a glance.

Platform-agnostic by design: each platform is a `Source` plugin. Currently working:
**YouTube** (video titles/descriptions + comments). **Reddit** is fully built but
dormant — see status below.

## Platform status

- **YouTube** — works today with a free API key.
- **Reddit** — Reddit closed self-serve OAuth app registration in late 2025
  (their "Responsible Builder Policy"); new access now requires a manual approval
  ticket with reportedly high rejection rates. The `RedditSource` (PRAW-based) is
  fully implemented and will work unchanged the moment you have approved
  `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` in `.env` — no code changes needed.

## How it works

1. **Plan** — Gemini turns your broad `--industry` / `--category` / `--country` inputs
   into concrete search phrases (in users' own language) and platform community hints
   (subreddits for Reddit, channel/topic phrases for YouTube).
2. **Fetch** — the chosen `Source` searches using those terms/hints and pulls matching
   content (posts+comments for Reddit; videos+comments for YouTube).
3. **Extract** — Gemini reads each item and pulls out explicit problem statements.
4. **Bucket** — Gemini clusters all extracted problems into labeled themes with example
   quotes and links.
5. **Report** — a summary prints to the terminal; full results (raw items, problems,
   buckets) save as JSON under `runs/`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
```

Fill in `.env`:
- `YOUTUBE_API_KEY` — in Google Cloud Console: create/select a project, enable
  **YouTube Data API v3**, create an API key under Credentials. Free tier: 10,000
  quota units/day (a run of this tool uses a few hundred).
- `GEMINI_API_KEY` — from https://aistudio.google.com/apikey. Can be the same Google
  Cloud project as your YouTube key, but needs the Gemini API enabled/its own key.
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — leave blank until you have
  Reddit-approved access (see Platform status above).

## Run

```bash
python main.py --industry "Fintech" --category "Personal budgeting apps" --country "India" --platform youtube
```

Optional flags: `--platform youtube|reddit` (default `youtube`), `--num-search-terms 10`
(exact count of planned search phrases), `--items-per-query 5` (videos per search term on
YouTube / submissions per subreddit search on Reddit), `--comments-per-item 8` (comments
per video / per submission), `--include-shorts` (YouTube Shorts are excluded by default),
`--min-views N` (YouTube only — skip videos under N views; default 0 = no filter).

## Web UI

A local browser UI is available as an alternative to the CLI — same pipeline, with a
form, a live progress log, and browsable results (including raw items/problems, not
just bucket summaries).

```bash
python webapp.py
```

Open http://127.0.0.1:5050. Single-user, local-only (Flask dev server, in-memory job
state) — not meant to be exposed beyond your machine.

## Architecture / adding a new platform

```
models.py                    RawItem, ProblemStatement, Bucket — platform-agnostic data shapes
query_planner.py             broad inputs -> search terms + community hints (via Gemini)
sources/base.py              Source ABC: from_env() + fetch() -> list[RawItem]
sources/reddit_source.py     Reddit implementation (PRAW) — built, pending API access
sources/youtube_source.py    YouTube implementation (YouTube Data API v3)
sources/registry.py          platform name -> Source class lookup
bucketing/extractor.py       RawItems -> ProblemStatements -> Buckets (via Gemini)
pipeline.py                  wires plan -> fetch -> extract -> bucket
reporting/formatter.py       CLI summary + JSON export
main.py                      CLI entrypoint
webapp.py                    local web UI (Flask) — same pipeline, browser frontend
```

To add another platform (forums, app store reviews, ...):
1. Create `sources/<name>_source.py` with a class implementing `Source.from_env()` and
   `Source.fetch()`, returning `RawItem`s.
2. Register it in `sources/registry.py`'s `SOURCES` dict.
3. Add it to `main.py`'s `--platform` choices.

Nothing in `query_planner.py`, `bucketing/`, or `pipeline.py` needs to change.

## Notes

- `runs/*.json` and `.env` are gitignored — never commit real credentials or output that
  might contain personal usernames/content you don't want to keep around.
- YouTube comments on some videos are disabled; the source skips those gracefully.
