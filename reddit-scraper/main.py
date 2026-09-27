import argparse

import netfix  # noqa: F401 — must import before anything opens a network connection
from dotenv import load_dotenv

from pipeline import run
from reporting.formatter import print_summary, save_csv, save_json


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Find and bucket problems users state on Reddit (and, later, other platforms)."
    )
    parser.add_argument("--industry", required=True, help='e.g. "Fintech"')
    parser.add_argument("--category", required=True, help='e.g. "Personal budgeting apps"')
    parser.add_argument("--country", required=True, help='e.g. "India"')
    parser.add_argument(
        "--platform",
        default="youtube",
        choices=["reddit", "youtube"],
        help="reddit requires Reddit-approved API access (self-serve is currently closed); youtube works with a free API key",
    )
    parser.add_argument(
        "--num-search-terms",
        type=int,
        default=10,
        help="How many search phrases the planner generates (mixed neutral/positive/negative). Default: 10.",
    )
    parser.add_argument(
        "--items-per-query",
        type=int,
        default=5,
        help="Videos to fetch per search term on YouTube (submissions per subreddit search on Reddit). Default: 5.",
    )
    parser.add_argument(
        "--comments-per-item",
        type=int,
        default=8,
        help="Max comments to fetch per video on YouTube (per submission on Reddit). Default: 8.",
    )
    parser.add_argument(
        "--include-shorts",
        action="store_true",
        help="Include YouTube Shorts in results. By default Shorts are excluded (not applicable to Reddit).",
    )
    parser.add_argument(
        "--min-views",
        type=int,
        default=0,
        help="Only include YouTube videos with at least this many views (not applicable to Reddit). Default: 0 (no filter).",
    )
    args = parser.parse_args()

    result = run(
        args.industry,
        args.category,
        args.country,
        args.platform,
        num_search_terms=args.num_search_terms,
        items_per_query=args.items_per_query,
        comments_per_item=args.comments_per_item,
        exclude_shorts=not args.include_shorts,
        min_views=args.min_views,
    )
    print_summary(result)
    json_path = save_json(result)
    csv_path = save_csv(result)
    print(f"Full results saved to {json_path}")
    print(f"Flat CSV (one row per problem) saved to {csv_path}")


if __name__ == "__main__":
    main()
