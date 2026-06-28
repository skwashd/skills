#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Batch-check PyPI packages: latest version, yanked status, age, python req.

Usage:
    uv run --script check_versions.py fastapi torch transformers

Uses `uv run --script` so it executes in a self-contained, valid Python
environment regardless of the system interpreter. Relies only on the
standard library (no third-party dependencies), and parses responses with
strict=False so PyPI descriptions containing raw control characters (which
break `jq`) do not abort the lookup.
"""
import json, sys, datetime, urllib.request

pkgs = sys.argv[1:]
if not pkgs:
    print("usage: check_versions.py <package> [<package> ...]", file=sys.stderr)
    sys.exit(2)

now = datetime.datetime.now(datetime.UTC)
for pkg in pkgs:
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=10) as r:
            d = json.loads(r.read().decode(), strict=False)
    except Exception as e:
        print(f"{pkg}: LOOKUP FAILED {e}")
        continue
    v = d["info"]["version"]
    rel = d["releases"].get(v, [])
    yanked = rel[0]["yanked"] if rel else "?"
    ut = rel[0]["upload_time"] if rel else None
    age = "?"
    if ut:
        uploaded = datetime.datetime.fromisoformat(ut).replace(tzinfo=datetime.UTC)
        hrs = int((now - uploaded).total_seconds() // 3600)
        age = f"{hrs}h"
    print(f"{pkg}: latest={v} yanked={yanked} age={age} requires_python={d['info']['requires_python']}")
