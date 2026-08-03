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
license: MIT
compatibility: >
  Prefers the GitHub CLI (`gh`) authenticated against github.com for resolving action
  SHAs; falls back to `curl` + `jq` against api.github.com, which is rate-limited to
  60 requests/hour unauthenticated. Network access to api.github.com required.
metadata:
  author: skwashd
  version: "2.0.0"
---

# GitHub Actions Security

Guidance for hardening GitHub Actions workflows, drawn from Astral's production security practices
(the team behind Ruff and uv). Apply these checks when writing, reviewing, or auditing workflow
files.

---

## 1. Forbid Dangerous Triggers

**Never use `pull_request_target` or `workflow_run`.** These triggers run with write permissions
in the context of the *base* repository, even when initiated by a fork — making them almost
impossible to use safely. Real-world attacks on Ultralytics, tj-actions, Nx, and Trivy (see §11)
all exploited this.

The pattern is known as a **"pwn request"**: a privileged trigger combined with a checkout of
attacker-controlled fork code, so that code from an unmerged pull request executes with the base
repository's token and secrets. As of 2026 `actions/checkout` blocks the most common form of this
by default (see §2), but that is a backstop, not a licence to use these triggers.

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
- uses: actions/checkout@v7

# ✅ Immutable — locked to an exact commit
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
  with:
    persist-credentials: false
```

**Always set `persist-credentials: false` on checkout actions.** By default, `actions/checkout`
saves the authentication token in the local git config, where subsequent steps can read and
abuse it. Disabling this limits credential exposure if a later step is compromised.

### `actions/checkout` Now Blocks Pwn Requests — Make Sure You Have That Version

Since `v7.0.0` (June 2026), `actions/checkout` **refuses by default to check out fork pull
request code** under `pull_request_target` or `workflow_run`. It detects the telltale unsafe
inputs and fails rather than fetching attacker-controlled code into a privileged context:

```yaml
# All of these are now blocked by default under pull_request_target / workflow_run
ref: refs/pull/${{ github.event.pull_request.number }}/merge
ref: ${{ github.event.pull_request.head.sha }}
repository: ${{ github.event.pull_request.head.repo.full_name }}
```

The fix was backported on 2026-07-16 to `v2`, `v3.7.0`, `v4.4.0`, `v5.1.0` and `v6.1.0`, with
`v7.0.1` following on 2026-07-17. **Anything older does not have it.**

**This is the cost of pinning, and you have to pay it deliberately.** Hash-pinning means upstream
security fixes do *not* reach you automatically — a workflow pinned to a pre-July-2026
`actions/checkout` commit is still running the old permissive behaviour today. Pinning buys you
protection against a compromised upstream at the price of owning your own update cadence. That
is the right trade, but only if something actually drives the updates: pair every pinned action
with Dependabot's `github-actions` ecosystem (§8), which updates the SHA *and* rewrites the
trailing version comment.

**Treat `allow-unsafe-pr-checkout: true` as a review blocker.** It is the opt-out input, named to
be greppable precisely so it shows up in review and static analysis. There is no configuration of
this repository's rules under which it is acceptable.

```yaml
# ❌ Re-enables the pwn request the block exists to prevent
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
  with:
    allow-unsafe-pr-checkout: true
```

**Know the limits of the backstop.** It protects `actions/checkout` only. A workflow that fetches
fork code with raw `git`, with `gh pr checkout`, or through a third-party action reintroduces the
same vulnerability with none of the protection. §1 remains the actual rule; this is defence in
depth beneath it.

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
gh api repos/actions/checkout/commits/v7.0.1 --jq '.sha'
```

**Always perform both steps.** Step 1 tells you what the latest version actually is (not what
you think it might be). Step 2 gives you the immutable hash for that version. Using a real hash
for an outdated version is almost as bad as guessing — it means missing security fixes.

The `/commits/{ref}` endpoint handles both lightweight and annotated tags correctly — it
always resolves to the underlying commit, skipping the tag object indirection.

**Fallback with `curl` and `jq`** (when `gh` is unavailable):

```bash
# Find latest release tag
curl -sf https://api.github.com/repos/actions/checkout/releases/latest | jq -r '.tag_name'

# Resolve tag to commit SHA
curl -sf https://api.github.com/repos/actions/checkout/commits/v7.0.1 | jq -r '.sha'
```

Note: unauthenticated GitHub API requests are rate-limited to 60/hour. Prefer `gh` when possible.

**No network access at all?** `git ls-remote` needs no API token and no authentication, and it is
the authoritative source for what a tag actually points at:

```bash
git ls-remote --tags https://github.com/actions/checkout | grep -E 'v7\.0\.1'
```

Watch for annotated tags here: `git ls-remote` shows the tag *object* on the `refs/tags/x` line
and the underlying commit on the `refs/tags/x^{}` line. **Pin the commit, not the tag object.**
Lightweight tags have no `^{}` line and point straight at the commit.

### Tooling

- Run [**zizmor**](https://github.com/zizmorcore/zizmor) locally and in CI — its `unpinned-uses` and `impostor-commit` audits
  catch both missing pins and commits that don't correspond to any real released state.
- Use [**pinact**](https://github.com/suzuki-shunsuke/pinact) to automatically convert tag-based references to SHA pins.
  Note that `v4.0.0` was a breaking release: version comments are now mandatory, the `-review`
  option was removed, and `-no-api` was added for validating pins offline.

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
  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
    with:
      persist-credentials: false
  - uses: aws-actions/configure-aws-credentials@...   # authenticates here
  - run: cargo build                                   # unrelated — but has AWS creds
  - run: cargo test                                    # unrelated — but has AWS creds
  - run: aws s3 cp target/release/app s3://my-bucket/  # actual usage

# ✅ Credential obtained immediately before use — no unrelated steps exposed
steps:
  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
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
This catches security regressions at review time, including `unpinned-uses`, `impostor-commit`,
`template-injection`, and `dependabot-cooldown` (see §8).

**Use zizmor `1.28.0` or later.** Version `1.27.0` shipped a logging defect that exposed
configured GitHub tokens in cleartext in zizmor's own logs **when debug-level logging was enabled**
— a single `-v`/`--verbose` flag, or a matching `RUST_LOG` directive, was enough to trigger it
(GHSA-f42p-wjw5-97qh). No other version was affected. The debug-logging precondition makes this
less severe than it first sounds, but CI runs are exactly where someone turns verbosity up to
debug a failure, so treat the floor as firm. If a repo pins zizmor, check the pin before anything
else.

**Pin the zizmor version, not just the action.** `zizmorcore/zizmor-action` takes a `version:`
input that **defaults to `latest`**, so SHA-pinning the action still leaves it downloading whatever
zizmor is current at run time. This is precisely the immutability gap described in §2 — an
immutably-pinned action making a mutable decision at runtime — and it means an unpinned `version:`
would have silently picked up 1.27.0 during the window it was vulnerable. Set it explicitly:

```yaml
- uses: zizmorcore/zizmor-action@<sha> # vX.Y.Z
  with:
    version: "1.29.0"
```

A complete reference workflow that implements every rule in this skill lives at
[`examples/zizmor.yml`](examples/zizmor.yml). Read that file only when you actually need to
scaffold a new workflow into a target repo — it is a copy-paste artifact, not narrative content.
Before copying, look up the current SHAs for `actions/checkout` and `zizmorcore/zizmor-action`
using the procedure in §2, and the current zizmor release; the pins recorded in the example will
go stale.

**Set the path trigger to `.github/**`**, not just `.github/workflows/**`. This ensures changes
to `dependabot.yml` and the zizmor config (see §8) are also gated by the workflow:

```yaml
on:
  pull_request:
    paths:
      - '.github/**'
  push:
    branches: [main]
    paths:
      - '.github/**'
```

### Audits That Do Not Fire by Default

zizmor sorts audits into personas, and a default run is `--persona=regular`. Several audits worth
having simply do not run unless you ask for them — a clean default report is not the same as a
clean pedantic one:

| Audit | Persona required | Why you want it |
|---|---|---|
| `stale-action-refs` | `pedantic` | Flags SHA pins whose version comment no longer matches any release — the classic symptom of a pin that was never updated. |
| `self-hosted-runner` | `pedantic` | Self-hosted runners on public repos are reachable by fork PRs. |
| `secrets-outside-env` | `auditor` | Secrets referenced outside an `env:` block, widening exposure. |

Run `zizmor --persona=pedantic .github/workflows/` periodically even if CI stays on the default
persona, and say which persona a clean result came from when reporting one.

### Two Audits to Configure Deliberately

- **`forbidden-uses`** — an allow or deny list for `uses:` references. This is the practical way
  to enforce an organisational action allowlist locally, without waiting on org-level policy:

  ```yaml
  rules:
    forbidden-uses:
      config:
        allow:
          - actions/*
          - zizmorcore/*
  ```

- **`secrets-inherit`** — flags `secrets: inherit` on reusable workflow calls, which hands the
  callee every secret the caller can see rather than the ones it needs. It ships an autofix that
  rewrites the call to forward secrets explicitly. Take the autofix.

---

## 8. Set a Dependabot Cooldown (and align zizmor)

**Configure a Dependabot `cooldown` to delay adopting brand-new releases.** Without a cooldown,
Dependabot opens a PR the moment a release is published — giving you no time to observe whether
the upstream was compromised (as happened with tj-actions, Ultralytics and Trivy). A delay of a
few days allows the community to catch most compromised or broken releases before you merge them.

GitHub now applies a **3-day cooldown by default**, even when `cooldown` is absent from the
config entirely. Set it explicitly at 3 days anyway: writing anything shorter produces a config
that looks stricter than the platform default while actually being weaker, and stating the value
gives you an obvious place to raise it.

Add a `cooldown` block to every Dependabot ecosystem entry in `.github/dependabot.yml`:

```yaml
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 3    # matches the platform default; raise semver-major-days for stricter control
    labels:
      - "dependencies"
      - "actions"
```

> **Note:** `cooldown` applies to version updates only — security updates are never delayed.

**Keep the daily schedule.** The cooldown runs from each release, not from a fixed point in the
week, so on an active upstream there is always a sliding window of releases becoming eligible.
Daily picks each one up the day it clears; weekly batches them into one large PR up to six days
late for no security benefit.

### Align zizmor's `dependabot-cooldown` audit

zizmor's `dependabot-cooldown` audit **defaults to requiring 7 days** and flags anything lower
as a finding. To run a 3-day cooldown without a standing finding, set the threshold explicitly
in `.github/zizmor.yml` (auto-discovered by zizmor in the `.github/` directory, and by the
`zizmorcore/zizmor-action` in CI):

```yaml
# zizmor config — https://docs.zizmor.sh/configuration/
# Keep this value in sync with cooldown.default-days in .github/dependabot.yml.
rules:
  dependabot-cooldown:
    config:
      days: 3
```

**Keep `rules.dependabot-cooldown.config.days` equal to `cooldown.default-days`** in
`dependabot.yml` so the policy and the check always agree. If you raise the Dependabot cooldown
later, raise the zizmor threshold to match.

Be honest about what this is: lowering a check's threshold to match your policy is only
legitimate when the policy is deliberate. Three days is a considered trade between vetting time
and patch latency, and it is the platform floor. **Never lower this below 3** — at that point you
are suppressing the warning rather than answering it, and the config is weaker than having no
`cooldown` block at all.

---

## 9. Recommended Tools

| Tool | Purpose |
|------|---------|
| [**zizmor**](https://github.com/zizmorcore/zizmor) | Static analysis for GitHub Actions — catches `unpinned-uses`, `impostor-commit`, `template-injection`, `secrets-inherit`, `dependabot-cooldown`, and ~35 more. Run locally and in CI. **Requires ≥ 1.28.0** (see §7). |
| [**pinact**](https://github.com/suzuki-shunsuke/pinact) | Automatically converts tag/branch action references to full SHA pins. `v4.0.0+` requires version comments and drops `-review`. |

---

## 10. Quick Review Checklist

When reviewing a workflow file, verify each of the following:

- [ ] No `pull_request_target` or `workflow_run` triggers
- [ ] No steps that post comments to PRs or issues — use job summaries or logs instead
- [ ] All `uses:` references are pinned to a full 40-char SHA (looked up, never guessed)
- [ ] All checkout actions use `persist-credentials: false`
- [ ] `actions/checkout` is pinned to `v7.0.0` or later, or to one of the 2026-07-16 backports (`v2`, `v3.7.0`, `v4.4.0`, `v5.1.0`, `v6.1.0`), so the pwn-request block is present
- [ ] No `allow-unsafe-pr-checkout: true` anywhere
- [ ] No fork PR code is fetched by raw `git`, `gh pr checkout`, or a third-party action
- [ ] No `secrets: inherit` on reusable workflow calls — secrets are forwarded explicitly
- [ ] All jobs use `runs-on: ubuntu-24.04` (never `ubuntu-latest`)
- [ ] `permissions: {}` at the top of every workflow file
- [ ] Per-job permissions grant only what is strictly necessary
- [ ] Authentication steps appear immediately before the step that uses the credentials
- [ ] Sensitive secrets are in deployment environments, not at repo level
- [ ] Release jobs require manual approval and do not use caching
- [ ] Dependabot config sets a `cooldown` (`default-days ≥ 3`) on every ecosystem entry
- [ ] `.github/zizmor.yml` sets `rules.dependabot-cooldown.config.days` to match the Dependabot cooldown, and never below 3
- [ ] zizmor is ≥ 1.28.0 and passes cleanly (no `unpinned-uses`, `impostor-commit`, `template-injection`, `secrets-inherit`, or `dependabot-cooldown` findings)
- [ ] A `--persona=pedantic` run has been done at least once (see §7)
- [ ] A zizmor CI workflow exists with path trigger `.github/**`
- [ ] No `aquasecurity/trivy-action` (see §11)

---

## 11. Case Studies — Why These Rules Exist

Each of these is a real 2026 incident that maps directly onto a rule above. Cite them when a
reviewer pushes back on the cost of a rule.

### Trivy / `aquasecurity/trivy-action` — §1 and §2, and a lesson in incident response

A two-stage compromise, and the clearest argument in this document.

**Stage one (February 2026)** was a textbook pwn request. A workflow used a privileged trigger
and checked out the fork pull request head, letting attacker-controlled code run with the base
repository's token. That is precisely the pattern §1 forbids and the one `actions/checkout` now
blocks by default.

**Stage two (March 2026)** was worse, and it was not another pwn request. After the first
disclosure, credentials were rotated — but the rotation **was not atomic**, and the attacker held
a valid token through the rotation window. They used it to force-push **76 of 77 version tags** in
`aquasecurity/trivy-action` to malicious commits. The blast radius reached the Trivy VSCode
extension, Docker images, and downstream PyPI packages.

Two lessons, and the second is the one people skip:

1. **Every consumer pinned to a tag was compromised. Every consumer pinned to a commit SHA was
   not.** §2 is not theoretical.
2. **Credential rotation that is not atomic is not rotation.** If an attacker can hold a live
   token across the rotation, you have announced the breach without ending it. Revoke first,
   verify revocation, then issue new credentials — and treat every artifact published during the
   exposure window as suspect until proven otherwise.

**This repository's position: do not use `aquasecurity/trivy-action`.** The vulnerability was
ordinary and forgivable; the handling was not. A supply-chain security vendor that ships a pwn
request, then botches the rotation badly enough to hand the attacker its own tag namespace, has
not earned a place in a trusted CI pipeline. Where a vulnerability scanner is genuinely needed,
choose a different one and pin it by SHA like everything else.

Note also that many published write-ups conflate the two stages and describe the March tag hijack
as itself a pwn request. It wasn't. Getting this right matters, because the two stages have
different fixes: §1 prevents stage one, and competent incident response prevents stage two.

### `actions-cool/issues-helper` — §2, as a controlled experiment

In May 2026 every tag in the repository was redirected to a single imposter commit, which pulled
down a runtime, scraped credentials from runner memory, and exfiltrated them. 53 tags moved.

What makes this worth citing is how cleanly it separated the two populations: **workflows pinned
to a known-good full commit SHA were unaffected; only those referencing version tags were
compromised.** Same action, same window, same attacker — the only variable was the pin. If
someone argues SHA pinning is cargo-culted ceremony, this is the answer.

The secondary lesson is about §1's ban on PR-commenting workflows: `issues-helper` exists to
comment on issues and PRs, which is exactly the capability that made it worth compromising and
exactly the capability §1 tells you not to grant a third-party action in the first place.
