# Sitecheck

Crawls a site and reports broken links.

## Installation

```bash
uv tool install sitecheck
```

## Usage

```bash
sitecheck https://www.example.com --depth 3
```

Options:

- `--depth` — maximum crawl depth (default 2).
- `--format` — output format, `text` or `json` (default `text`).

Exit code is 0 when no broken links are found, 1 otherwise.
