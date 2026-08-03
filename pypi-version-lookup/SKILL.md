---
name: pypi-version-lookup
description: Query the PyPI JSON API to look up the latest stable version of any Python package. Use this skill whenever you need to check a package's current version, for example when writing or updating requirements.txt, pyproject.toml, setup.cfg, Dockerfiles, CI configs, or any dependency specification. Also trigger when the user asks "what's the latest version of X", "is there a newer version of X", or when pinning, bumping, or updating Python dependencies.
allowed-tools: Read Write Edit Glob Grep Bash(curl *) Bash(jq *) Bash(python3 *) Bash(uv run *)
license: MIT
compatibility: >
  Requires curl and jq on PATH, plus network access to pypi.org. The batch script
  additionally requires uv (which provisions its own Python >= 3.11). A python3
  fallback is documented for environments without jq.
metadata:
  author: skwashd
  version: "2.0.0"
---

# PyPI Version Lookup

Look up the latest published version of a Python package from the PyPI JSON API using `curl` and `jq`.

## Dependencies

This skill shells out to `curl` and `jq`. Both are required.

- Debian / Ubuntu: `apt install jq` (curl is usually preinstalled)
- macOS: `brew install jq`
- Alpine: `apk add jq curl`

If `jq` is unavailable in the target environment, fall back to a Python one-liner that uses only the standard library:

```bash
curl -sSf --max-time 15 -A "$PYPI_UA" "https://pypi.org/pypi/requests/json" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])'
```

## Always Identify Yourself

PyPI's API documentation asks consumers to send an identifying `User-Agent` with contact
information. There is no rate limiting at the CDN edge today, but PyPI explicitly reserves the
right to block consumers for irresponsible activity — and an unlabelled default `curl/8.x` making
bursts of requests from an agent loop is exactly the profile that gets blocked.

Set this once and use it in every request in this skill:

```bash
PYPI_UA="skwashd-skills/pypi-version-lookup (+https://github.com/skwashd/skills)"
```

Substitute your own repository or contact address when using this outside that project.

### Robust batch lookup (recommended for multiple packages)

When checking several packages at once — or when `jq` chokes on PyPI
descriptions containing raw control characters, or when the system `python3`
is broken/missing — use the bundled [`check_versions.py`](check_versions.py).
It runs via `uv run --script` (PEP 723 inline metadata), so `uv` provisions a
valid, self-contained Python environment regardless of the host interpreter,
and it depends only on the standard library:

```bash
uv run --script check_versions.py fastapi torch transformers ruff
# fastapi: latest=0.136.3 yanked=False age=331h requires_python=>=3.10
# ...
```

It reports the latest version, yanked status, release age, and `requires_python`
for each package in one pass, and exits non-zero if any lookup failed or any
package is yanked. Pass `--max-age-hours 24` to also fail on releases younger
than the cooldown window (see below), which makes it usable directly as a CI or
pre-commit gate:

```bash
uv run --script check_versions.py --max-age-hours 24 fastapi ruff
```

Three reasons it exists rather than another `curl | jq` pipeline:

- It parses with `json.loads(..., strict=False)`, so the raw control characters
  that PyPI allows in package descriptions — and that make `jq` abort — don't
  break the lookup.
- It uses `upload_time_iso_8601` and timezone-aware UTC datetimes throughout, so
  the age arithmetic is right regardless of the local timezone.
- It reports a non-zero exit status on failure, rather than relying on the caller
  to check a pipeline correctly (see the pipeline trap below).

## How it works

Query the PyPI JSON API for a package and extract the `info.version` field, which reflects the latest stable release.

```bash
curl -sSf --retry 3 --max-time 15 -A "$PYPI_UA" \
  "https://pypi.org/pypi/<package>/json" | jq -er '.info.version'
```

Replace `<package>` with the exact PyPI package name (e.g., `requests`, `numpy`, `flask`).

### Flags explained

- `-s` — Silent mode; suppresses the progress meter.
- `-S` — But still print errors. `-s` alone swallows the diagnostic along with the progress bar, which makes failures much harder to explain to the user. Always pair them.
- `-f` — Fail on HTTP errors, returning a non-zero exit code instead of writing an HTML error page to stdout.
- `--retry 3` — curl's own retry with backoff, covering transient 5xx, 408, 429 and connection failures. This replaces a hand-rolled retry loop. **Do not add `--retry-all-errors`** — despite the name suggesting robustness, it makes curl retry a 404 as well, so every typo'd or missing package costs three pointless backoff rounds (measured: ~7s versus ~0.08s). A missing package will not appear on the third try.
- `--max-time 15` — Abort if the entire request (including retries of a single attempt) takes too long.
- `-A "$PYPI_UA"` — Identify the consumer, as PyPI's docs request.
- `jq -e` — Exit non-zero if the result is `null` or `false`, so a missing field is an error rather than the literal string `null`.

### Detecting failure correctly — read this before copying any pipeline

**`$?` after a pipeline is the exit status of the *last* command, not of `curl`.** This bites here
specifically, and it is silent:

```bash
# ❌ BROKEN — reports success for a package that does not exist
version=$(curl -sf --max-time 5 "https://pypi.org/pypi/${pkg}/json" | jq -r '.info.version')
if [ $? -eq 0 ]; then ...   # $? is jq's status
```

When the package is missing, `curl -f` exits non-zero and writes nothing. `jq` then reads empty
input, prints nothing, and **exits 0**. The test passes and `$version` is the empty string. A
typo'd package name looks exactly like a successful lookup.

Two fixes, and it costs nothing to use both:

```bash
set -o pipefail                    # $? becomes the rightmost non-zero status in the pipeline
jq -er '.info.version'             # -e turns null/empty results into a non-zero exit
```

With `pipefail`, a failing `curl` is no longer masked by a succeeding `jq`. (Precisely: the
pipeline's status is that of the last command to exit non-zero, so `(exit 5) | (exit 3)` gives 3
and `(exit 5) | (exit 0)` gives 5. Either way, curl's failure surfaces.)

Every example below assumes `set -o pipefail` is in effect.

**`pipefail` does not cross a process substitution.** `read x < <(cmd | cmd)` gives you `read`'s
status, not the pipeline's — so check the `read` itself, as the yanked example below does.

### Handling multiple packages

When looking up several packages at once, run the lookups in a loop. Prefer
[`check_versions.py`](check_versions.py) for anything more than a couple of packages — it does
this in one pass and reports more.

```bash
set -o pipefail
for pkg in requests flask numpy; do
  if version=$(curl -sSf --retry 3 --max-time 15 -A "$PYPI_UA" \
                 "https://pypi.org/pypi/${pkg}/json" | jq -er '.info.version'); then
    echo "${pkg}==${version}"
  else
    echo "${pkg}: lookup failed" >&2
  fi
done
```

Note the shape: `if version=$(...)` tests the assignment's exit status directly, which — with
`pipefail` set — is non-zero whenever any command in the pipeline failed. There is no separate
`$?` check to get wrong.

## Error handling and retries

Network blips happen. `curl --retry 3` handles them without a wrapper, backing off between
attempts and covering transient 5xx, 408 and 429 responses as well as connection failures:

```bash
lookup_version() {
  local pkg="$1"
  local version

  set -o pipefail
  version=$(curl -sSf --retry 3 --max-time 15 -A "$PYPI_UA" \
              "https://pypi.org/pypi/${pkg}/json" | jq -er '.info.version') || {
    echo "Failed to fetch version for '${pkg}'." >&2
    return 1
  }
  printf '%s\n' "$version"
}
```

A 404 is not retried, which is what you want — a missing package will not appear on the third
try. This is the reason `--retry-all-errors` is deliberately absent: it would retry the 404 too.

### Common failure causes

- **Package name typo** — PyPI names are case-insensitive but must otherwise match exactly. Some packages use hyphens on PyPI but underscores in import (e.g., `scikit-learn` on PyPI, `sklearn` in code). When unsure, try the hyphenated form first.
- **Network timeout** — `--max-time 15` bounds this, and `--retry 3` backs off and tries again.
- **Package doesn't exist** — curl returns a non-zero exit code thanks to `-f`. Detect it by testing the assignment directly (`if version=$(...)`) with `pipefail` set — **not** by checking `$?` after the pipeline, which reports jq's status. See "Detecting failure correctly" above.

## Example usage

Single package:

```bash
curl -sSf --retry 3 --max-time 15 -A "$PYPI_UA" \
  "https://pypi.org/pypi/requests/json" | jq -er '.info.version'
# → 2.34.2
```

With retry wrapper:

```bash
version=$(lookup_version "requests")
echo "requests==${version}"
# → requests==2.34.2
```

## What `info.version` actually guarantees

Worth knowing precisely, because it determines how much extra checking you need to do. The
endpoint sorts candidate releases by yanked status, then prerelease status, then version ordering,
and takes the first. In practice:

| Question | Answer |
|---|---|
| Can it return a prerelease when a stable release exists? | **No** — stable always wins. |
| Can it return a prerelease if the project has *only* prereleases? | **Yes** (e.g. nightly-only packages). |
| Can it return a yanked release? | **Only if every release of the project is yanked.** Yanked status is a sort key, not a filter. |
| Are quarantined (suspected-malware) releases excluded? | **Yes.** |

So `info.version` *is* the "latest non-yanked stable release" for essentially every real package,
with those two narrow exceptions. The checks below cover the exceptions; they are not routine
hazards.

## Yanked releases

A release on PyPI can be **yanked** after publication when the maintainer needs to discourage its
use (e.g., it shipped a regression or a security bug). Per the table above, `info.version` only
surfaces a yanked release when the entire project has been yanked — rare, but it does happen to
abandoned or withdrawn packages, and that is exactly the case you don't want to pin.

The top-level `.info.yanked` field answers this in the response you already have, with no second
request:

```bash
set -o pipefail
pkg="requests"

# Fetch once, then read fields out of the response.
json=$(curl -sSf --retry 3 --max-time 15 -A "$PYPI_UA" \
         "https://pypi.org/pypi/${pkg}/json") || {
  echo "lookup failed for ${pkg}" >&2
  exit 1
}
version=$(jq -er '.info.version' <<<"$json") || exit 1
yanked=$(jq -er '.info.yanked'  <<<"$json") || yanked=false

if [ "$yanked" = "true" ]; then
  echo "${pkg}==${version} is yanked, refusing to pin" >&2
  exit 1
fi
echo "${pkg}==${version}"
```

**Why not `read -r version yanked < <(curl … | jq …)`?** Because `pipefail` does not propagate out
of a process substitution — you get `read`'s status, not the pipeline's. On a missing package the
substitution produces nothing, both variables end up empty, the `yanked` test is false, and the
script prints `somepkg==` and **exits 0**. That is the same fail-open shape this document warns
about above, in the one snippet whose entire job is to be a gate. Fetch first, check the fetch,
then parse.

> Note `yanked=false` as the fallback on the second `jq`: `.info.yanked` is `false` for the vast
> majority of releases, and `jq -e` treats `false` as a non-zero exit. Without the fallback the
> script would abort on every healthy package.

**jq trap:** do not write `jq '.info.yanked // "absent"'` to defend against a missing field. In jq
the alternative operator `//` fires on `false` as well as `null`, so a perfectly good `false`
becomes `"absent"`. Use `has("yanked")` if you need to distinguish absent from false.

**Avoid the `.releases` key.** It is on PyPI's deprecated list — the docs say projects should move
to the Index API and that the key "may be removed entirely from this API response." It has already
been removed from the per-version endpoint. If you need to walk releases to find the highest
non-yanked one, prefer the Index API (see below), where `yanked` is exposed per file.

## Fresh-release cooldown (24 hours)

A version that was uploaded in the last 24 hours has had no time to be vetted by the wider community. Compromised maintainer accounts and accidental bad releases are most often caught within the first day. Refuse to pin anything younger than that, and pin the previous release instead.

The PyPI JSON API exposes upload times under `urls[]`. **Use `upload_time_iso_8601`, not
`upload_time`** — the two look interchangeable and are not:

```
upload_time         : "2026-05-14T19:25:26"            <- naive: no offset, no fractional seconds
upload_time_iso_8601: "2026-05-14T19:25:26.443000Z"    <- explicit Z (UTC), microsecond precision
```

Both are UTC, but only the second *says* so. Most date libraries will parse the first as local
time, silently shifting the computed age by your timezone offset — which in Australia is enough
to slip a 14-hour-old release past a 24-hour check.

Take the earliest upload time across the release's files rather than `[0]`, since file order in
the response is not guaranteed:

```bash
set -o pipefail
pkg="requests"
json=$(curl -sSf --retry 3 --max-time 15 -A "$PYPI_UA" \
         "https://pypi.org/pypi/${pkg}/json")
version=$(jq -er '.info.version' <<<"$json")
upload_time=$(jq -er '[.urls[].upload_time_iso_8601] | min' <<<"$json")

age=$(( $(date -u +%s) - $(date -u -d "${upload_time}" +%s) ))
if [ "$age" -lt 86400 ]; then
  echo "${pkg}==${version} is only $((age/3600))h old; refusing to pin" >&2
  exit 1
fi
echo "${pkg}==${version}"
```

Note this fetches the JSON once and queries it twice with a here-string, rather than making two
requests for the same document.

If the latest release is too fresh, use the Index API to find the highest non-yanked version
whose upload time is more than 24 hours ago (see below) — `.releases` on the JSON API would also
work but is deprecated.

On macOS / BSD, `date -u -d` is not available. Use
`python3 -c 'import datetime,sys; print(int(datetime.datetime.fromisoformat(sys.argv[1]).timestamp()))' "$upload_time"`
as a portable replacement for the second `date` call. With `upload_time_iso_8601` this works
directly — `fromisoformat` understands the trailing `Z` on Python 3.11+, and the result is
correctly timezone-aware, which is not true if you feed it the bare `upload_time`.

## Looking up a specific version

The PyPI JSON API also exposes per-version metadata at `https://pypi.org/pypi/{package}/{version}/json`. Use this when you need to confirm a specific version exists, fetch its release date, or check its `requires_python` constraint without pulling every release.

```bash
# Confirm requests==2.31.0 exists and print its upload time
curl -sSf --max-time 15 -A "$PYPI_UA" "https://pypi.org/pypi/requests/2.31.0/json" \
  | jq -er '[.urls[].upload_time_iso_8601] | min'
# → 2023-05-22T15:12:42.313790Z
```

A non-zero exit code from `curl -f` means the package or version does not exist. Note that
`.releases` is **not** present on this per-version endpoint — it was removed for stability
reasons — which is a good reminder not to build on that key at all.

## Check project status before pinning anything new

PyPI publishes a project-level status marker (PEP 792) that says whether a project is still a
reasonable thing to depend on. It is exposed on the **Index API**, not the legacy JSON API:

```bash
curl -sSf --max-time 15 -A "$PYPI_UA" \
  -H 'Accept: application/vnd.pypi.simple.v1+json' \
  "https://pypi.org/simple/requests/" | jq -er '."project-status".status'
# → active
```

| Status | Meaning | What to do |
|---|---|---|
| `active` | Normal. | Proceed. |
| `archived` | Maintainer has stopped releasing. | Pin if you must, but flag it — no future fixes are coming. |
| `quarantined` | **Suspected malware.** PyPI has blocked installation. | Refuse to pin. Escalate to the user. |
| `deprecated` | Planned status, not yet implemented. | Treat like `archived`. |

For a skill whose job is "should I pin this?", a quarantined project is a far more serious finding
than a yanked version. Check it when introducing a dependency the user has not used before; it is
not worth an extra request on routine version bumps of packages already in the tree.

## When to reach for the Index API instead

The Index (Simple) API is the interface PyPI recommends for new integrations. Request it as JSON:

```bash
curl -sSf --max-time 15 -A "$PYPI_UA" \
  -H 'Accept: application/vnd.pypi.simple.v1+json' \
  "https://pypi.org/simple/requests/" | jq -c '.files[-1] | {filename, yanked, "requires-python", "upload-time"}'
```

Per file it gives you `yanked`, `requires-python`, `upload-time` (always UTC, per PEP 700), `size`,
hashes, and `provenance` (PEP 740 attestations). It also carries a top-level `versions` list.

**Use it for** walking release history — finding the highest non-yanked version, or the newest
version older than the cooldown window — and for `project-status`. This is the replacement for the
deprecated `.releases` key.

**Do not use it** for the simple "what's the latest version" question. Its `versions` list is a
flat array of strings with no yanked flag (yanked is per *file*), and PEP 700 states the ordering
is not significant — so reproducing what `info.version` gives you for free means mapping filenames
back to versions and sorting by PEP 440 yourself. Stick with `info.version` for the common case.

## Extra info available from the API

The `.info` object has more than just `version`. Useful fields if needed:

- `.info.summary` — One-line package description
- `.info.requires_python` — Python version constraint (e.g., `>=3.8`); may be `null`
- `.info.home_page` or `.info.project_urls` — Links to docs/repo
- `.info.license` — License string
- `.info.yanked` and `.info.yanked_reason` — Whether *this* release has been yanked, and why

Example — get version and Python requirement together:

```bash
curl -sSf --max-time 15 -A "$PYPI_UA" "https://pypi.org/pypi/flask/json" \
  | jq -er '"\(.info.version) (requires Python \(.info.requires_python // "unspecified"))"'
# → 3.1.3 (requires Python >=3.9)
```

## Caching

Responses carry `cache-control: max-age=900` and an `etag`, and PyPI honours conditional requests
(`If-None-Match` returns `304`). For one-off lookups this does not matter. If you are checking the
same packages repeatedly — a CI matrix, a loop over a large requirements file — respect the
15-minute window rather than re-fetching, and identify yourself properly (see above). The
`x-pypi-last-serial` response header is a cheap change-detection signal if you want one.
