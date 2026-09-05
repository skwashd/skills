# Payments Gateway

Issue tracker: Jira (project DAVE)

## Checks

- `go test ./...`

## Deploy

Every merge to `main` runs through GitHub Actions, which builds the image and pushes
to the production cluster. `gh` is used throughout this repo for release management —
tagging releases, checking workflow runs, and cutting changelogs.
