---
name: ci-failure-triage
description: Diagnose and fix a failing CI build from a GitHub Actions run/job URL, a PR with failing checks, or a pasted CI log — whether the code broke or the runner environment did. Use this whenever the user says CI, the build, the pipeline, or the checks are failing, pastes a github.com/.../actions/runs/... URL or a CI error log, asks why a workflow/job/step failed, or reports environment-shaped CI trouble — a job failing on a commit that previously passed, failures only on a specific runner label (ubuntu-*-arm, macos-*, windows-*), 429 rate limits, "no space left on device", or OIDC credential errors. Covers Bitbucket Pipelines and other CI systems too, even if the user only pastes the error with no explanation.
allowed-tools: Read Glob Grep Edit Write Bash(gh *)
license: MIT
compatibility: >
  Needs the GitHub CLI (gh), authenticated against the target repository, for
  GitHub Actions runs. Other CI systems work from pasted logs with no extra
  tooling.
metadata:
  author: skwashd
  version: "1.0.0"
---

# CI Failure Triage

Take a failing CI run from "here's the URL/log" to a verified green build — by finding the actual cause, not by weakening the checks.

## Step 1: Get the Evidence

Never diagnose from the error summary alone. Get the full log for the failing step first.

For GitHub Actions, use `gh` (never WebFetch — the HTML pages don't render logs):

```bash
gh run view <run-id> --log-failed              # failing steps only
gh run view <run-id> --json jobs               # job/step structure
gh pr checks <pr-number>                       # all checks on a PR
gh run list --workflow=<file> --limit 5        # is this new or chronic?
```

Run and job IDs come straight out of pasted URLs: `.../actions/runs/<run-id>/job/<job-id>`. A `#step:3:4` anchor means step 3, line 4 — jump there.

For CI systems without a CLI (Bitbucket Pipelines, TeamCity), ask the user to paste the full log of the failing step, and name exactly which step you need. The same applies whenever `gh` can't reach the run (no auth, private repo): stop, and give the user both the step you need and the exact copy-pasteable command that fetches it (e.g. `gh run view <run-id> --log-failed -R <owner>/<repo>`) — a handoff they can act on beats a description of what's missing.

Then open the workflow file and find the failing step's definition. The command CI actually ran — with its exact flags and versions — is your reproduction target.

## Step 2: Classify the Failure

Read the log and decide which of these you're looking at, because the fix strategy is completely different:

1. **Code/config regression** — the change in this PR broke a check. Most common. Fix the code.
2. **Runner/environment failure** — nothing in the repo changed, but the runner image, a preinstalled tool, network access, or disk did. Telltale sign: the same commit passed before, or the failure is in setup steps rather than your build. Read `references/runner-environment.md` — it has the playbooks (image/toolchain drift, shared-IP rate limiting, disk exhaustion, arm64, OIDC, cache).
3. **Upstream release breakage** — a floating dependency (an action tag, `latest` image, unpinned package) picked up a new release. The log shows a version you didn't change.
4. **Deploy-step failure** — the workflow succeeded until `terraform apply` / `cdk deploy` and the error is from AWS, not the workflow. Consult the `aws-failure-triage` skill.
5. **Flaky test/infra** — check run history (`gh run list`) before concluding this; "flaky" claimed without evidence is usually a real bug.

## Step 3: Reproduce Locally

Before changing anything, run the exact command the workflow runs, locally. Same tool, same version, same flags. If it passes locally but fails in CI, the delta between the two environments *is* the finding (version drift, missing env var, case-sensitive filesystem, arch difference) — chase that delta rather than editing code speculatively.

If it can't be reproduced locally (needs cloud creds, runner-only environment), say so and reason from the log — but then be explicit that the fix is a hypothesis and must be confirmed by the next run.

## Step 4: Fix the Root Cause

Fixes that are never acceptable, even though they turn CI green:

- **Unpinning or loosening a version** to make resolution succeed. The repo pins versions deliberately; the fix is to pin to the correct *new* exact version, not to a range or `latest`.
- **Suppressing a linter or type-checker finding** (`noqa`, `type: ignore`, rule config changes) — fix the finding.
- **Deleting or skipping the failing test.**
- **Adding blanket retries** to paper over nondeterminism.

For upstream breakage, the pattern is: identify the last-known-good and the current-stable versions, pin the exact stable version, and note the changelog entry that explains the break.

If you've made one fix attempt and the run failed again: stop. Write down what you tried, what the log said before and after, and what that rules out. Then form the next hypothesis. Repeating a variation of the same fix without new evidence is the failure mode that wastes the most time.

After touching any workflow file, run `zizmor` on it if it's available in the repo's tooling — workflow edits are a common way to introduce security regressions. For hardening beyond the immediate fix (pinning to SHAs, `permissions:`, dangerous triggers), that's the `github-actions-security` skill's territory.

## Step 5: Land It and Verify

How the fix lands matters:

- Ask before committing if the user hinted they manage the branch themselves ("I'll rebase it", "I'll commit it"). Some fixes are wanted as **fixup commits against a named SHA** (`git commit --fixup <sha>`) — do that when asked.
- After pushing, watch the run to completion: `gh run watch <run-id>` or re-check `gh pr checks`. The task is done when the run is green, not when the commit is pushed.

Report back: the failing step, the root cause in one sentence, what changed, and the green run's URL or status. If it's still red, say so and show the new error.
