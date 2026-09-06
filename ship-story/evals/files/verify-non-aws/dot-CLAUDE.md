# Reports Web

Web front end for the nightly reporting service.

Issue tracker: Jira (project DAVE)

## Checks

- `make lint`
- `make test`

## Deploy

Merging to `main` deploys the `reports-web` app to Fly.io via GitHub Actions. Tail
production logs with `flyctl logs -a reports-web`.
