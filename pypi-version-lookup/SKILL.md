---
name: pypi-version-lookup
description: Query the PyPI JSON API to look up the latest stable version of any Python package. Use this skill whenever you need to check a package's current version, for example when writing or updating requirements.txt, pyproject.toml, setup.cfg, Dockerfiles, CI configs, or any dependency specification. Also trigger when the user asks "what's the latest version of X", "is there a newer version of X", or when pinning, bumping, or updating Python dependencies.
allowed-tools: Bash(curl *) Bash(jq *) Bash(python3 *) Bash(uv run *)
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
curl -sf --max-time 5 "https://pypi.org/pypi/requests/json" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])'
```

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

It reports the latest version, yanked status, release age (for the 24h
cooldown check below), and `requires_python` for each package in one pass.
It parses responses with `json.loads(..., strict=False)` so the control-character
issue that breaks `jq` does not abort the lookup, and uses timezone-aware
UTC datetimes (`datetime.now(datetime.UTC)`) to compute age.

## How it works

Query the PyPI JSON API for a package and extract the `info.version` field, which always reflects the latest stable release.

```bash
curl -sf --max-time 5 "https://pypi.org/pypi/<package>/json" | jq -r '.info.version'
```

Replace `<package>` with the exact PyPI package name (e.g., `requests`, `numpy`, `flask`).

### Flags explained

- `-s` — Silent mode; suppresses progress output.
- `-f` — Fail silently on HTTP errors (returns a non-zero exit code instead of HTML error pages). This makes it easy to detect failures via `$?`.
- `--max-time 5` — Abort if the entire request takes longer than 5 seconds.

### Handling multiple packages

When looking up several packages at once, run the lookups in a loop:

```bash
for pkg in requests flask numpy; do
  version=$(curl -sf --max-time 5 "https://pypi.org/pypi/${pkg}/json" | jq -r '.info.version')
  if [ $? -eq 0 ] && [ -n "$version" ] && [ "$version" != "null" ]; then
    echo "${pkg}==${version}"
  else
    echo "${pkg}: lookup failed" >&2
  fi
done
```

## Error handling and retries

Network blips happen. If a lookup fails (non-zero exit code, empty result, or the string `"null"`), retry up to 3 times with exponential backoff before giving up:

```bash
lookup_version() {
  local pkg="$1"
  local attempt=0
  local max_retries=3
  local version=""

  while [ $attempt -lt $max_retries ]; do
    version=$(curl -sf --max-time 5 "https://pypi.org/pypi/${pkg}/json" | jq -r '.info.version')
    if [ $? -eq 0 ] && [ -n "$version" ] && [ "$version" != "null" ]; then
      echo "$version"
      return 0
    fi
    attempt=$((attempt + 1))
    sleep $((2 ** attempt))  # 2s, 4s, 8s backoff
  done

  echo "Failed to fetch version for '${pkg}' after ${max_retries} attempts." >&2
  return 1
}
```

### Common failure causes

- **Package name typo** — PyPI names are case-insensitive but must otherwise match exactly. Some packages use hyphens on PyPI but underscores in import (e.g., `scikit-learn` on PyPI, `sklearn` in code). When unsure, try the hyphenated form first.
- **Network timeout** — The 5-second max-time handles this. The retry logic above will back off and try again.
- **Package doesn't exist** — curl will return a non-zero exit code thanks to `-f`. Check `$?` to detect this.

## Example usage

Single package:

```bash
curl -sf --max-time 5 "https://pypi.org/pypi/requests/json" | jq -r '.info.version'
# → 2.32.3
```

With retry wrapper:

```bash
version=$(lookup_version "requests")
echo "requests==${version}"
# → requests==2.32.3
```

## Yanked releases

A release on PyPI can be **yanked** after publication when the maintainer needs to discourage its use (e.g., it shipped a regression or a security bug). The `info.version` field can in some cases still point at a yanked release. Before pinning the value you got back, check whether it has been yanked:

```bash
pkg="requests"
version=$(curl -sf --max-time 5 "https://pypi.org/pypi/${pkg}/json" | jq -r '.info.version')
yanked=$(curl -sf --max-time 5 "https://pypi.org/pypi/${pkg}/json" \
  | jq -r --arg v "$version" '.releases[$v][0].yanked')

if [ "$yanked" = "true" ]; then
  echo "${pkg}==${version} is yanked, refusing to pin" >&2
  exit 1
fi
echo "${pkg}==${version}"
```

If the latest version is yanked, prefer the highest non-yanked release listed under `.releases` rather than pinning the yanked one anyway.

## Fresh-release cooldown (24 hours)

A version that was uploaded in the last 24 hours has had no time to be vetted by the wider community. Compromised maintainer accounts and accidental bad releases are most often caught within the first day. Refuse to pin anything younger than that, and pin the previous release instead.

The PyPI JSON API exposes upload times under `urls[].upload_time`. The check below uses GNU `date` to compute the age in seconds and aborts when it is below 86400.

```bash
pkg="requests"
version=$(curl -sf --max-time 5 "https://pypi.org/pypi/${pkg}/json" | jq -r '.info.version')
upload_time=$(curl -sf --max-time 5 "https://pypi.org/pypi/${pkg}/${version}/json" \
  | jq -r '.urls[0].upload_time')

age=$(( $(date -u +%s) - $(date -u -d "${upload_time}Z" +%s) ))
if [ "$age" -lt 86400 ]; then
  echo "${pkg}==${version} is only $((age/3600))h old; refusing to pin" >&2
  exit 1
fi
echo "${pkg}==${version}"
```

If the latest release is too fresh, walk back through `.releases` and pick the highest non-yanked version whose upload time is more than 24 hours ago.

On macOS / BSD, `date -u -d` is not available. Use `python3 -c 'import datetime,sys; print(int(datetime.datetime.fromisoformat(sys.argv[1]).timestamp()))' "$upload_time"` as a portable replacement for the second `date` call.

## Looking up a specific version

The PyPI JSON API also exposes per-version metadata at `https://pypi.org/pypi/{package}/{version}/json`. Use this when you need to confirm a specific version exists, fetch its release date, or check its `requires_python` constraint without pulling every release.

```bash
# Confirm requests==2.31.0 exists and print its upload time
curl -sf --max-time 5 "https://pypi.org/pypi/requests/2.31.0/json" \
  | jq -r '.urls[0].upload_time'
# → 2023-05-22T15:12:44
```

A non-zero exit code from `curl -f` means the package or version does not exist.

## Extra info available from the API

The `.info` object has more than just `version`. Useful fields if needed:

- `.info.summary` — One-line package description
- `.info.requires_python` — Python version constraint (e.g., `>=3.8`)
- `.info.home_page` or `.info.project_urls` — Links to docs/repo
- `.info.license` — License string

Example — get version and Python requirement together:

```bash
curl -sf --max-time 5 "https://pypi.org/pypi/flask/json" | jq -r '"\(.info.version) (requires Python \(.info.requires_python))"'
# → 3.1.0 (requires Python >=3.9)
```
