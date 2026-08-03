#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Batch-check PyPI packages: latest version, yanked status, age, python req.

Usage:
    uv run --script check_versions.py fastapi torch transformers
    uv run --script check_versions.py --max-age-hours 24 fastapi torch

Exit status:
    0  every package looked up cleanly and passed the checks
    1  a lookup failed, or a package is yanked, or --max-age-hours was given
       and a package is too fresh or its age could not be determined
    2  bad arguments (argparse)

The age check fails closed: with --max-age-hours set, a package whose upload
time cannot be read is reported as AGE UNKNOWN and treated as a failure. That
makes the script safe to use directly as a gate in CI or a pre-commit hook.

Uses `uv run --script` so it executes in a self-contained, valid Python
environment regardless of the system interpreter. Relies only on the
standard library (no third-party dependencies), and parses responses with
strict=False so PyPI descriptions containing raw control characters (which
break `jq`) do not abort the lookup.
"""

import argparse
import datetime
import json
import sys
import urllib.error
import urllib.request

UA = "skwashd-skills/pypi-version-lookup (+https://github.com/skwashd/skills)"
TIMEOUT = 15


def fetch(pkg: str) -> dict:
    """Fetch a project's JSON metadata, identifying ourselves as PyPI asks."""
    req = urllib.request.Request(
        f"https://pypi.org/pypi/{pkg}/json",
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        # strict=False tolerates raw control characters in package descriptions,
        # which are valid on PyPI and make `jq` abort.
        return json.loads(r.read().decode(), strict=False)


def uploaded_at(data: dict) -> datetime.datetime | None:
    """Earliest upload time across the latest release's files, as aware UTC.

    Uses upload_time_iso_8601 (explicit `Z`) rather than upload_time (naive),
    so fromisoformat returns a timezone-aware value and the age arithmetic is
    correct regardless of the local timezone. Takes the minimum rather than
    urls[0] because file order in the response is not guaranteed.
    """
    times = [
        u["upload_time_iso_8601"]
        for u in data.get("urls", [])
        if u.get("upload_time_iso_8601")
    ]
    if not times:
        return None
    return datetime.datetime.fromisoformat(min(times))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check latest version, yanked status and age for PyPI packages."
    )
    parser.add_argument("packages", nargs="+", metavar="PACKAGE")
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=None,
        metavar="H",
        help="fail if the latest release is younger than H hours (cooldown check)",
    )
    args = parser.parse_args()

    now = datetime.datetime.now(datetime.UTC)
    failed = False

    for pkg in args.packages:
        try:
            data = fetch(pkg)
        except urllib.error.HTTPError as e:
            print(f"{pkg}: LOOKUP FAILED HTTP {e.code}", file=sys.stderr)
            failed = True
            continue
        except Exception as e:  # network, DNS, malformed JSON
            print(f"{pkg}: LOOKUP FAILED {e}", file=sys.stderr)
            failed = True
            continue

        info = data["info"]
        version = info["version"]
        yanked = bool(info.get("yanked", False))
        requires_python = info.get("requires_python") or "unspecified"

        uploaded = uploaded_at(data)
        if uploaded is None:
            age_hours = None
            age = "?"
        else:
            age_hours = (now - uploaded).total_seconds() / 3600
            age = f"{int(age_hours)}h"

        notes = []
        if yanked:
            # info.version only surfaces a yanked release when every release of
            # the project is yanked, so this is a strong signal, not a nitpick.
            notes.append("YANKED")
            failed = True
        if args.max_age_hours is not None:
            if age_hours is None:
                # Fail closed. If this is being used as a gate, an unknown age
                # must not silently pass — that is the failure mode the gate
                # exists to prevent.
                notes.append("AGE UNKNOWN")
                failed = True
            elif age_hours < args.max_age_hours:
                notes.append(f"TOO FRESH (<{args.max_age_hours:g}h)")
                failed = True

        suffix = "  " + " ".join(notes) if notes else ""
        print(
            f"{pkg}: latest={version} yanked={yanked} age={age} "
            f"requires_python={requires_python}{suffix}"
        )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
