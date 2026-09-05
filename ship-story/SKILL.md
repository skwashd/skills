---
name: ship-story
description: Take a single story or ticket from Jira, Linear, or GitHub Issues to verified deployment — read the ticket, branch, implement, open a pull request, watch CI, diagnose failed runs from their logs, merge, confirm the deploy, and verify the deployed behaviour against the acceptance criteria before closing. Use this skill whenever the user asks to implement, work on, pick up, start, build or ship a story, ticket or issue, or names a work item key such as PROJ-123, ENG-45 or #123, even if they do not say which tracker, or mention GitHub or deployment. Use it for any task where the finishing condition is "the change is live and confirmed working" rather than "the code is written".
allowed-tools: Read Write Edit Glob Grep WebFetch Bash
license: MIT
compatibility: >
  Assumes git and the GitHub CLI (`gh`, authenticated) are on PATH for every project.
  Beyond that, the tracker in use decides what else is needed: the Atlassian CLI (`acli`,
  authenticated) and the jira-acli skill for Jira; the Linear CLI (`linear`,
  authenticated) for Linear, with the linear-cli skill for anything beyond the ship-time
  commands; nothing further for GitHub Issues. Verification tooling — a cloud
  provider's CLI, browser automation, or whatever else a project's checks need — depends
  on the project and is not assumed. Project-specific lint, test and build commands are
  read from the repository's CLAUDE.md rather than assumed.
metadata:
  author: skwashd
  version: "2.0.0"
---

# Ship a story

One story, start to finish, in a single session. The session has no memory of other
stories — everything needed comes from the ticket and the repository.

**What this skill assumes is available:** `git` and `gh`, always. Which tracker CLI, and
which verification tooling, depend on the project — see "Which tracker" below, and
steps 4 and 8.
What it deliberately does *not* assume is the project's own toolchain — the lint,
type-check, test and build commands come from `CLAUDE.md` (step 4), because those differ
per repository and a hardcoded list is wrong more often than it is right.

## The finishing condition

A story is done when the change is deployed and you have **observed** the acceptance
criteria being met. Not when the code is written, not when the PR is merged, not when
the pipeline is green. When you have watched the thing work.

This matters because the most common way agentic work fails is finishing early —
reporting a correct-looking diff as a completed outcome. Hold the line on this.

## Which tracker

Work happens on Jira, Linear or GitHub Issues depending on the project. Determine which
one applies **once, at the start of the session**, and don't re-derive it per step.

Check, in order, stopping at the first hit:

1. **The user said, or gave a URL.** A `*.atlassian.net/browse/…` link is Jira; a
   `linear.app/…/issue/…` link is Linear; a `github.com/…/issues/N` link or a bare `#N`
   is GitHub Issues.
2. **An `Issue tracker:` line in the project's `CLAUDE.md`** — e.g. `Issue tracker:
   Linear (team ENG)`. Read `CLAUDE.md` anyway for step 4; check for this line while
   you're there.
3. **Repo config left by the tracker's own tooling.** `.linear.toml` (written by `linear
   config`) means Linear. `.jira/` (written by the jira-acli skill) means Jira.
4. **Otherwise, ask.** Name the trackers and let the user pick.

Two rules that matter more than the list above:

- **Never infer the tracker from the key's shape.** `ABC-123` is a valid key on both
  Jira and Linear. Guessing wrong doesn't fail loudly — it reads, or worse comments on,
  a real ticket in the wrong system.
- **Never infer the tracker from which CLI is installed.** `gh` in particular is
  installed on most projects for reasons that have nothing to do with issue tracking —
  its presence says nothing about whether GitHub Issues is the tracker in use.

Once determined, read the matching file before doing anything else in this skill:

| Tracker | Read first | For anything deeper |
|---|---|---|
| Jira | `references/tracker-jira.md` | Call the Skill tool with `jira-acli` |
| Linear | `references/tracker-linear.md` | Call the Skill tool with `linear-cli` |
| GitHub Issues | `references/tracker-github.md` | — (`gh issue` covers it) |

Each adapter gives the tracker-specific answer for every step below: how to resolve the
key, read the work item, name the branch, shape the commit and PR, comment, and close.
Where a step below says "per the adapter", that file has the answer.

## Writing style

Australian English, in everything you write — commit messages, the PR body, and any
comment or update posted back to the tracker. Acceptance criteria, wherever you state or
restate them, are phrased as observable outcomes: "submitting the form returns a 200 and
a message appears in the queue", not "the form works".

## The loop

### 1. Read the ticket

Resolve the work item per the adapter, then read it: summary, description, acceptance
criteria, and the parent epic's constraints if any.

If the acceptance criteria are empty or vague, stop and ask. Do not infer them and
proceed — you will implement against the wrong target and only discover it at
verification, having wasted a full cycle.

Restate to the user, before writing code:

- What you are building
- Which acceptance criteria you will verify, and how you will verify each
- What you will show them when it is done

### 2. Branch

```bash
git checkout main && git pull
git checkout -b <branch-name>
```

The branch name comes from the adapter — for most trackers this is the bare work item
key, exactly as it appears (`PROJ-123`, `ENG-45`), with no case change, slug or
appended text. Some trackers generate their own branch name as part of starting work;
where the adapter says to use that, use it verbatim rather than hand-rolling one, since
downstream integrations often match on the exact name.

### 3. Implement

Follow `CLAUDE.md`. Read it if you have not already — it is not optional context.

Stay inside the story. If you notice something else that wants fixing, note it for the
user rather than fixing it. A PR that does two things is harder to verify and harder to
demonstrate.

If the change touches anything under `.github/`, call the Skill tool with
`github-actions-security` and apply its rules — pinned SHAs, minimal `permissions:`, no
`pull_request_target`. A workflow edit slipped into a feature PR is the easiest way to
regress those.

Every commit follows the adapter's convention for referencing the work item — the exact
form (bracketed key in the subject line, a trailer in the body, or something else)
differs per tracker, so check the adapter rather than assuming the shape from a
different one. Jira's, for reference:

```
[PROJ-123] Add server-side validation to the contact form
```

Further detail goes in the commit body after a blank line.

### 4. Check locally before pushing

**Get the commands from `CLAUDE.md`.** Every repository has its own formatter, linter,
type checker, test runner and build step, and running the wrong ones is worse than running
none — it produces false confidence. `CLAUDE.md` is the contract; read the checks out of
it and run them in the order it gives.

If `CLAUDE.md` does not list them, infer from the repository and **say what you inferred**
so the user can correct it. Reasonable places to look:

| Signal | Likely checks |
|---|---|
| `.pre-commit-config.yaml` | `pre-commit run --all-files` — usually the complete set |
| A `Makefile` / `justfile` / `Taskfile.yml` | `make check`, `just test`, or whatever the targets are named |
| `pyproject.toml` | the project's own formatter/linter/test runner via its package manager |
| `package.json` scripts | `npm run lint`, `npm test`, `npm run build` |
| A CI workflow under `.github/workflows/` | **the most reliable source** — whatever CI runs is exactly what you need to pass |

That last row is the fallback worth reaching for first when `CLAUDE.md` is silent: read
the workflow and run locally what the pipeline will run remotely.

A pipeline failure you could have caught locally costs a full deploy cycle. Fix everything
here first.

If the change is user-facing, exercise it locally before pushing — serve the site or run
the app however `CLAUDE.md` describes. Use browser automation — whichever tool or skill
the session provides — for anything involving form interaction or a multi-step path.

### 5. Open the pull request

```bash
git push -u origin HEAD
gh pr create --title "<per adapter>" --body-file pr-body.md
```

**Write the title and body explicitly; do not use `--fill`.** `--fill` only uses the
commit message when the branch has exactly one commit. With more than one it derives the
title from a humanised branch name — and since branches are typically named after the
bare work item key, a multi-commit `PROJ-123` branch produces a PR titled **"Proj 123"**.
`--fill` also cannot produce the third thing the body needs, below.

The PR body must:

- reference the work item key, in the adapter's convention
- describe what changed
- list what you intend to verify after deployment, criterion by criterion

That last list is the contract for step 8. Writing it before the deploy makes it much
harder to quietly narrow the definition of done afterwards.

### 6. Watch the checks

```bash
gh pr checks --watch --fail-fast
```

Use this rather than `gh run watch`. Two reasons, both of which matter in an
agent session:

- `gh pr checks` resolves the PR from the current branch, so it needs no run ID.
  `gh run watch` requires one unless it can prompt a human, and errors out otherwise.
- **`gh pr checks` exits non-zero on failure by default** — 1 when a check failed, 8 when
  checks are still pending, 0 when everything passed. `gh run watch` exits **0 even when
  the run failed** unless you pass `--exit-status`. Relying on it means walking straight
  past a red pipeline into the merge step.

`--fail-fast` stops at the first failure, which also guarantees the run has finished
before you ask for its logs — `gh run view` refuses to return logs for a run still in
progress.

**When it fails, read the logs. Do not guess.**

```bash
run_id=$(gh run list --branch "$(git rev-parse --abbrev-ref HEAD)" \
  --limit 1 --json databaseId --jq '.[0].databaseId')
gh run view "$run_id" --log-failed
```

The explicit `run_id` is not optional: `gh run view --log-failed` also requires a run ID
non-interactively, for the same reason as above.

That gives you the failing job's output directly. Read it, form a specific hypothesis
about the cause, fix that, and push. Never push a speculative change hoping the result
differs — if two attempts have not resolved it, stop and report what the logs actually
say.

Other useful invocations:

```bash
gh run list --limit 5
gh run view <run-id> --log
gh pr checks --json name,state,bucket
```

### 7. Merge

Confirm with the user before merging. Then:

```bash
gh pr merge --merge --delete-branch
```

Two things that look like failures and are not:

- **If the base branch has a merge queue, `--delete-branch` is rejected outright.** Drop
  the flag and use `--auto` instead; the queue handles the merge and the branch cleanup.
- **A failed *remote* branch deletion is noise, not a failed merge.** Branch protection can
  forbid the delete while the merge itself succeeded. Check whether the PR is merged before
  treating the message as an error.

Watch the deployment run to completion. A merged PR is not a deployed change.

### 8. Verify against the acceptance criteria

This is the part that cannot be skipped or summarised.

Work through the acceptance criteria one at a time. For each, run something that
produces evidence.

**Prefer read-only observation.** These change nothing:

- **Site reachable** — `curl -sI https://<domain>` and read the status and headers
- **Redirect** — `curl -sI http://<domain>` and confirm the 301
- **Structured logs** — tail the deployed service's logs with whatever the platform
  provides
- **Resource state** — query the platform for whatever the criteria name: queue depth,
  stack or deployment contents, job status
- **Browser path** — browser automation, whichever tool or skill the session provides,
  for anything involving form interaction

The commands behind the middle bullets are platform-specific. **If the project deploys
to AWS, read `references/verify-aws.md` first** — it has the observation commands and a
trap where a read-sounding command mutates production state. On any other platform, get
the commands from `CLAUDE.md` or the platform's own docs, and apply the same test to
each before running it: know, don't assume, which side of read-only it falls on.

**Some verification necessarily writes. Name it when it does:**

- **Live endpoint** — `curl -s -X POST <url> -d '<payload>'`. This is a real request
  against a real environment. It may create records, trigger downstream events, or cost
  money. Use obviously-synthetic test data, and say in your report what it created.
- **Read-sounding commands that mutate.** Every platform has commands that read like
  observation but change state. Consuming from a queue is the canonical case: on most
  platforms a "receive" hides the message from genuine consumers for a timeout and
  increments the delivery counter that dead-letter policies act on — peeking repeatedly
  at a production queue can push a legitimate message into the DLQ. Prefer the
  depth/attribute query; if you truly need a message body, use the platform's
  peek-without-consuming option if it has one, and tell the user either way.

The rule is not "never mutate" — it is **never mutate silently, and never mutate to
work around a permissions boundary**. If a verification step writes, it goes in the
report as a thing you did, not as a detail you omit.

### 9. Report

State, per acceptance criterion: what you ran, what came back, whether it passed.

If something did not pass, say so plainly. A story that is 90% done and honestly
reported is more useful than one reported as complete that fails when shown to someone.

Include anything your verification wrote — test records created, messages received — so
the user can clean up if they need to.

Then close the work item per the adapter, with a comment recording what was verified.
**Check first whether the merge already closed or transitioned it** — several trackers
do this automatically, and re-closing or re-transitioning an already-closed item is
noise, not a safety net. Verify the end state rather than assuming either way.

## Hitting the permissions boundary

You will, at some point, be unable to do something because your credentials for the
deployment environment do not permit it. **This is the system working, not a problem to
solve.**

Say what was blocked, why, and how the change will reach the environment instead —
which is always: through the pipeline. Then do that.

Never look for another credential, never ask the user to run the mutating command for
you, never suggest widening the policy. If a task genuinely cannot be expressed as a
pipeline deployment, stop and say so — that is real information, not a blocker to route
around.

## Confirm before

- Merging a pull request
- Force pushing anything
- Changing repository or workflow settings
- Deleting a branch other than the one just merged
- Any tracker status change or bulk operation on the tracker

## Failure modes to avoid

- **Declaring done at green CI.** Green means it deployed, not that it works.
- **Trusting a command that cannot fail.** Some tools exit 0 on failure unless told
  otherwise — `gh run watch` is the example this skill used to get wrong. Before relying
  on any check to gate a decision, know what it does on failure.
- **Verifying by reading the code.** Verification is observation, not inspection.
- **Speculative re-pushes.** Read the failure, then fix the failure.
- **Scope drift.** Adjacent improvements go in the report, not the PR.
- **Silent assumptions.** If you filled a gap in the ticket with a judgement call, say
  which gap and which call. The same applies to a gap in tracker detection.
- **Unreported side effects.** If verification wrote something, it goes in the report.
- **Guessing the tracker from the key.** `ABC-123` doesn't tell you which system it's
  in. See "Which tracker" above.
