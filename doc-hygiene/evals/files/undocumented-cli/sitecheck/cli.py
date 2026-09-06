"""sitecheck command line interface."""

import argparse
import os
import sys

from sitecheck.checker import check_site


def main() -> int:
    parser = argparse.ArgumentParser(prog="sitecheck", description="Check a site for broken links.")
    parser.add_argument("url", help="Base URL to crawl")
    parser.add_argument("--depth", type=int, default=2, help="Maximum crawl depth")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the URLs that would be checked without fetching them",
    )
    args = parser.parse_args()

    token = os.environ.get("SITECHECK_TOKEN")

    results = check_site(
        args.url,
        depth=args.depth,
        dry_run=args.dry_run,
        auth_token=token,
    )
    print(results.render(args.format))
    return 0 if results.ok else 1


if __name__ == "__main__":
    sys.exit(main())
