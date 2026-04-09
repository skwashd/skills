---
name: github-actions-security
description: >
  Apply battle-tested GitHub Actions security hardening to CI/CD workflows. Use this skill
  whenever a user asks about securing GitHub Actions, writing or reviewing workflow YAML files,
  setting up CI/CD pipelines, hardening release processes, managing workflow permissions or secrets,
  pinning actions, or anything related to supply chain security in GitHub-based projects. Also
  trigger when the user shares a workflow file and asks for a review, or mentions tools like
  zizmor or pinact.
allowed-tools: Read Write Edit WebFetch Bash(gh *) Bash(curl *) Bash(jq *)
---

# GitHub Actions Security

Guidance for hardening GitHub Actions workflows, drawn from Astral's production security practices
(the team behind Ruff and uv). Apply these checks when writing, reviewing, or auditing workflow
files.

---

## 1. Forbid Dangerous Triggers

**Never use `pull_request_target` or `workflow_run`.** These triggers run with write permissions
in the context of the *base* repository, even when initiated by a fork — making them almost
impossible to use safely. Real-world attacks on Ultralytics, tj-actions, and Nx all exploited this.

**What to do instead:**
- Always use `pull_request` for contributor-triggered workflows. It runs in a sandboxed,
  unprivileged context with no access to secrets.
- **Never post comments on PRs or issues from a workflow.** This is explicitly forbidden — it is
  the most common reason projects reach for `pull_request_target`, but it is never worth the risk.
  Instead, surface results via [job summaries](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary) or workflow logs.

```yaml
# ❌ Avoid
on:
  pull_request_target:
  workflow_run:

# ✅ Prefer
on:
  pull_request:
```

**Job summary example** — write structured output that appears in the Actions UI without any
write permission to the repository:

```yaml
- name: Report results
  run: |
    echo "## Test Results" >> $GITHUB_STEP_SUMMARY
    echo "| Suite | Status |" >> $GITHUB_STEP_SUMMARY
    echo "|-------|--------|" >> $GITHUB_STEP_SUMMARY
    echo "| Unit  | ✅ Passed (142/142) |" >> $GITHUB_STEP_SUMMARY
    echo "| Integration | ❌ Failed (3/10) |" >> $GITHUB_STEP_SUMMARY
```

---

## 2. Pin All Actions to Full Commit SHAs

**Never reference actions by a mutable tag or branch** (e.g., `uses: actions/checkout@v6`).
Tags can be moved or deleted; branches can be force-pushed. An attacker who compromises an
upstream action can silently substitute malicious code.

**Always pin to the full 40-character commit SHA:**

```yaml
# ❌ Mutable — tag can be overwritten
- uses: actions/checkout@v6

# ✅ Immutable — locked to an exact commit
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
  with:
    persist-credentials: false
```

**Always set `persist-credentials: false` on checkout actions.** By default, `actions/checkout`
saves the authentication token in the local git config, where subsequent steps can read and
abuse it. Disabling this limits credential exposure if a later step is compromised.

### Looking Up the Correct SHA — Never Guess

**Never fabricate or guess a commit SHA, and never assume you know the latest version.** Both
the version tag and the hash must always be looked up from the actual repository. Use the
GitHub CLI (`gh`) to find the latest release and resolve its tag to the full commit SHA:

```bash
# Step 1: Find the latest release tag — do not skip this step
gh release list -R actions/checkout -L 5
```

```bash
# Step 2: Resolve that tag to the full commit SHA
gh api repos/actions/checkout/commits/v6.0.2 --jq '.sha'
```

**Always perform both steps.** Step 1 tells you what the latest version actually is (not what
you think it might be). Step 2 gives you the immutable hash for that version. Using a real hash
for an outdated version is almost as bad as guessing — it means missing security fixes.

The `/commits/{ref}` endpoint handles both lightweight and annotated tags correctly — it
always resolves to the underlying commit, skipping the tag object indirection.

**Fallback with `curl` and `jq`** (when `gh` is unavailable):

```bash
# Find latest release tag
curl -s https://api.github.com/repos/actions/checkout/releases/latest | jq -r '.tag_name'

# Resolve tag to commit SHA
curl -s https://api.github.com/repos/actions/checkout/commits/v6.0.2 | jq -r '.sha'
```

Note: unauthenticated GitHub API requests are rate-limited to 60/hour. Prefer `gh` when possible.

### Tooling

- Run [**zizmor**](https://github.com/zizmorcore/zizmor) locally and in CI — its `unpinned-uses` and `impostor-commit` audits
  catch both missing pins and commits that don't correspond to any real released state.
- Use [**pinact**](https://github.com/suzuki-shunsuke/pinact) to automatically convert tag-based references to SHA pins.

### Important Caveat

Hash-pinning is **necessary but not sufficient.** An immutably-pinned action can still make
*mutable decisions at runtime*, such as downloading the latest binary from a GitHub release.
Manually review action dependencies for these "immutability gaps" and work with upstreams to
embed cryptographic hashes for any downloaded binaries.

### Actions Without Tagged Releases

**Strongly prefer not to use actions that have no versioned releases.** An action that ships only
from a branch (e.g., `main`) signals that the maintainer is not treating releases as auditable
events. Look for an alternative action with proper release tags first; rolling your own inline
`run:` step is often the safer answer.

If you have already evaluated alternatives and still need to use such an action, **pin a specific
commit SHA from the upstream repository directly** — do not fork. Forking creates a parallel
history that diverges silently, hides upstream security fixes from your own dependency review,
and shifts the maintenance burden onto whoever inherits the workflow. A direct SHA pin against
the upstream is honest about what you depend on, and `dependabot` and `zizmor` can both reason
about it.

Resolve the upstream commit with `gh` and record both the SHA and a one-line justification in a
comment next to the `uses:` line so future reviewers understand why the action has no version
tag:

```bash
gh api repos/owner/action/commits/main --jq '.[0].sha'
```

```yaml
# No tagged releases upstream as of 2026-04-09; pinned directly to main HEAD.
# Re-evaluate alternatives during the next quarterly workflow audit.
- uses: owner/action@<full-40-char-sha>
```

---

## 3. Pin the Runner to a Specific Ubuntu Version

**Always use `runs-on: ubuntu-24.04`, never `ubuntu-latest`.** The `latest` label is a moving
pointer — when GitHub advances it to a new OS version, your workflow silently runs on a different
environment, which can break builds or introduce unexpected behaviour.

```yaml
# ❌ Unpredictable — silently changes when GitHub updates the alias
jobs:
  build:
    runs-on: ubuntu-latest

# ✅ Consistent — locked to a known environment
jobs:
  build:
    runs-on: ubuntu-24.04
```

This applies to every job, including test, lint, and release jobs.

The same principle applies to non-Ubuntu runners: pin `macos-26`, `windows-2025`, or whichever
specific image tag the workflow needs, and never use the `-latest` alias.

---

## 4. Apply Minimal Permissions

Default GitHub Actions permissions are far too broad. Always start from zero at the workflow level
and grant only what each individual job needs.

**At the workflow level — always start from zero:**
```yaml
permissions: {}   # deny all by default
```

**At the job level — grant only what that job actually needs:**
```yaml
jobs:
  build:
    permissions:
      contents: read   # only what's required
  release:
    permissions:
      contents: write
      id-token: write  # for OIDC / Trusted Publishing
```

---

## 5. Authenticate as Late as Possible

**Any step that obtains credentials — OIDC tokens, cloud provider sessions, API keys, registry
logins — must appear immediately before the step that uses them, with no unrelated steps in
between.**

Every step that runs while credentials are active is a step that can leak or abuse them. By
authenticating at the last possible moment, you minimise the number of steps in the blast radius
if any one of them is compromised.

```yaml
# ❌ Credential obtained too early — two unrelated steps run with an active AWS session
steps:
  - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
    with:
      persist-credentials: false
  - uses: aws-actions/configure-aws-credentials@...   # authenticates here
  - run: cargo build                                   # unrelated — but has AWS creds
  - run: cargo test                                    # unrelated — but has AWS creds
  - run: aws s3 cp target/release/app s3://my-bucket/  # actual usage

# ✅ Credential obtained immediately before use — no unrelated steps exposed
steps:
  - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
    with:
      persist-credentials: false
  - run: cargo build
  - run: cargo test
  - uses: aws-actions/configure-aws-credentials@...   # authenticates here
  - run: aws s3 cp target/release/app s3://my-bucket/  # immediately after
```

**The review rule is simple:** for every authentication step, check that the very next step is
the one that consumes those credentials. If there are unrelated steps between authentication and
usage, move the authentication step down.

---

## 6. Isolate Secrets with Deployment Environments

**Never use repo-level secrets for sensitive operations.** If any job in any workflow is
compromised, those secrets are exposed to every job.

**Use GitHub deployment environments and environment-scoped secrets instead:**

```yaml
jobs:
  test:
    runs-on: ubuntu-24.04
    # No environment — no access to release secrets

  publish:
    runs-on: ubuntu-24.04
    environment: release          # secrets scoped here only
    steps:
      - uses: pypa/gh-action-pypi-publish@...
```

This limits the blast radius: a compromised test or lint job cannot reach the secrets needed to
publish release artifacts.

**For release environments specifically**, layer these additional controls:
- **Require manual approval** from at least one other privileged team member before the
  environment activates. This prevents a single rogue or compromised account from publishing.
- **Do not use caching** in release jobs — this prevents [cache poisoning attacks](https://adnanthekhan.com/2024/05/06/the-monsters-in-your-build-cache-github-actions-cache-poisoning/).

---

## 7. Add a zizmor CI Workflow

**Every repository should include a workflow that runs zizmor against proposed workflow changes.**
This catches security regressions at review time.

A complete reference workflow that implements every rule in this skill lives at
[`examples/zizmor.yml`](examples/zizmor.yml). Read that file only when you actually need to
scaffold a new workflow into a target repo — it is a copy-paste artifact, not narrative content.
Before copying, look up the current SHAs for `actions/checkout` and `zizmorcore/zizmor-action`
using the procedure in §2; the pins recorded in the example will go stale.

---

## 8. Recommended Tools

| Tool | Purpose |
|------|---------|
| [**zizmor**](https://github.com/zizmorcore/zizmor) | Static analysis for GitHub Actions — catches `unpinned-uses`, `impostor-commit`, `template-injection`, and more. Run locally and in CI. |
| [**pinact**](https://github.com/suzuki-shunsuke/pinact) | Automatically converts tag/branch action references to full SHA pins. |

---

## 9. Quick Review Checklist

When reviewing a workflow file, verify each of the following:

- [ ] No `pull_request_target` or `workflow_run` triggers
- [ ] No steps that post comments to PRs or issues — use job summaries or logs instead
- [ ] All `uses:` references are pinned to a full 40-char SHA (looked up, never guessed)
- [ ] All checkout actions use `persist-credentials: false`
- [ ] All jobs use `runs-on: ubuntu-24.04` (never `ubuntu-latest`)
- [ ] `permissions: {}` at the top of every workflow file
- [ ] Per-job permissions grant only what is strictly necessary
- [ ] Authentication steps appear immediately before the step that uses the credentials
- [ ] Sensitive secrets are in deployment environments, not at repo level
- [ ] Release jobs require manual approval and do not use caching
- [ ] zizmor passes cleanly (no `unpinned-uses`, `impostor-commit`, or `template-injection` findings)
- [ ] A zizmor CI workflow exists targeting `.github/workflows/**`
