# Evals for `ci-failure-triage`

Test cases for the `ci-failure-triage` skill. Each eval is a realistic user prompt paired with input files (where applicable) and expectations describing what a good response should contain. Every case runs offline: the CI logs are captured fixtures, not live runs.

## Layout

```
evals/
├── evals.json
└── files/
    ├── lint-drift/       # ruff findings in a small Python project, workflow pins the tool
    ├── action-drift/     # golangci-lint-action floating on @master, v2 broke the config
    ├── image-drift/      # green + red logs from the same commit, runner image changed
    ├── rate-limit/       # 429s downloading a model on a hosted runner
    └── disk-full/        # ENOSPC during docker build, df output in the log
```

> **Fixture naming:** inside each fixture, `dot-github/` stands in for `.github/`. Storing a real
> `.github/` directory inside test fixtures causes trouble — tooling picks the files up as if they
> were this repo's own workflows. When running an eval, treat `dot-github/workflows/build.yml` as
> `.github/workflows/build.yml`; the prompts refer to the real paths.

`files` entries in `evals.json` name whole fixture directories, relative to the skill root.

## Test cases

| ID | Name | What it tests |
|----|------|---------------|
| 1 | `lint-failure-fix-not-suppress` | Fixes findings at the root cause; no `noqa`, no config loosening |
| 2 | `upstream-action-drift-pin-version` | Classifies upstream breakage; pins an exact version, not `@master` |
| 3 | `run-url-evidence-first` | Extracts run/job IDs from a URL; asks for logs instead of guessing |
| 4 | `runner-image-update-toolchain-drift` | Diagnoses environment drift by comparing green/red logs |
| 5 | `shared-runner-ip-rate-limit` | Shared egress IP diagnosis; rejects the naive secrets fix |
| 6 | `runner-disk-exhaustion` | Classifies ENOSPC as infrastructure, not a code bug |

## What each case is really guarding

**Eval 1** is the fix-not-suppress discipline. Two trivial ruff findings invite two trivial suppressions; the eval fails any `# noqa` or config change and expects the workflow's exact lint command to be re-run as verification.

**Eval 2** is upstream release breakage. The workflow floats on `@master`, and the fix that matters is the *pinning*, not the lint config — an answer that migrates the config but leaves `@master` in place will break again on the next major release.

**Eval 3** is the evidence-first rule under the worst conditions: a URL to a repository the agent cannot reach. The pass is a handoff — the exact `gh` command for the user to run — and the failure is a speculative fix invented from the URL's step anchor. It also checks the no-commit instruction is respected.

**Eval 4** is the same-commit-different-result scenario. The two logs differ in their `Set up job` headers (runner image version, preinstalled Node), and the expected diagnosis reads that delta rather than blaming the application code. The fix pins the toolchain with `setup-node`.

**Eval 5** guards against a security regression dressed as a fix: passing `HF_TOKEN` into a workflow that runs on fork PRs. The correct answer explains why CI hits limits a laptop never sees, proposes caching, and names the fork-secrets trap.

**Eval 6** tests classification: an integration-test job failing with ENOSPC is a runner problem, and the `df -h` output in the log is the evidence. Deleting or skipping tests is the failure mode.

## How to run

The [`skill-creator`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) plugin runs these, including with/without-skill benchmarking:

```
/plugin install skill-creator@claude-plugins-official
```

Spawn one subagent per eval with the skill loaded, then a baseline subagent without it, save outputs to `iteration-1/eval-<id>/{with,without}_skill/`, and grade against the expectations in `evals.json`. Copy each fixture directory into a scratch working directory first (restoring the `dot-` names) so runs don't modify the fixtures.

For an informal pass, run each prompt in a fresh session with the skill in scope and check the output against the expectations by hand.

## Expectation conventions

Expectations are plain-English statements about the response. They split into:

- **Positive coverage** — "identifies the root cause as X", "pins an exact version" — the response should do a specific thing.
- **Negative / no-false-positive** — "no `# noqa` is added", "does not propose `pull_request_target`" — the response should not take the tempting shortcut.
- **Process** — "the transcript shows the lint command being run" — about how the answer was reached, not just its text.

Evals 1 and 3 lean on process expectations; evals 5 and 6 are mostly about rejecting the wrong fix.
