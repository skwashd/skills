# Runner Environment Playbook

For failures caused by the runner or its environment rather than the repository's code. The defining symptom: the same commit passed before, or the failure happens before your build even starts.

## Confirm It's the Environment

Before reaching for these playbooks, establish that the code isn't the cause:

```bash
gh run list --workflow=<file> --limit 10 --json conclusion,headSha,createdAt
```

- Same SHA green earlier, red now → environment. Proceed here.
- First run of new code → probably a regression; go back to the main triage flow.

Then pull the environment facts from the log of the failing run. The **"Set up job"** step header records the runner image name and version (e.g. `ubuntu-24.04`, `Image Version: 20260830.1.0`) and links to the image's included-software manifest. Compare it against the last green run — an image version bump between green and red is your prime suspect.

## Playbooks by Symptom

### A Tool Behaves Differently and No One Changed It

Runner images ship preinstalled toolchains (Node, Go, Python, Docker, etc.) that GitHub updates roughly weekly. When an image update bumps a preinstalled tool, every repo relying on "whatever's on the runner" breaks at once, with no diff to blame.

Fix: stop depending on the preinstalled version. Pin the toolchain explicitly in the workflow (`actions/setup-go` / `setup-node` / `setup-python` with an exact version, matching what the project declares in go.mod / .nvmrc / pyproject.toml). The runner image is not a stable interface; setup actions with pins are.

### 429s / Rate Limiting / Throttled Downloads

Hosted runners share a small pool of egress IPs across all of GitHub's customers. External services (PyPI, Hugging Face, Docker Hub, apt mirrors) rate-limit those IPs, so your job gets 429s that never reproduce locally.

Fixes, in order of preference:
1. **Cache the artifact** (`actions/cache` or committing a lockfile-resolved bundle) so the download happens rarely.
2. **Authenticated requests** raise the rate limit — but only where the credential is safe: a secret used in a workflow that runs on fork PRs (`pull_request` from forks doesn't get secrets, but check for `pull_request_target` misuse) can be exfiltrated by a malicious PR. Never move a job to `pull_request_target` just to give it a token.
3. Mirror the artifact somewhere you control.

Retry loops are a last resort and must be bounded.

### "No space left on device" / ENOSPC

Hosted runners have ~14 GB of free disk. Docker layer accumulation, large caches, and build artifacts exhaust it.

Fix: delete what the job doesn't need at the start (the classic move is removing preinstalled bloat: android SDKs, dotnet, ghc under `/usr/local` and `/opt`), prune Docker between builds, shrink or split caches, or move to a larger runner. Check whether one recent addition (a new dependency, a new docker image) tipped it over — that's the real cause.

### Architecture-Specific Failures (arm64 Runners)

Jobs on `ubuntu-24.04-arm` (or arm64 self-hosted) fail where x86 passes: binary downloads hardcoded to amd64, Docker images without arm64 manifests, native Python/Node modules without prebuilt arm wheels.

Fix: make architecture explicit — detect `$(uname -m)` in download steps, verify base images are multi-arch, and for native deps either use versions with arm64 wheels or build them. Don't silently move the job back to x86 without flagging the cost trade-off the arm runner was chosen for.

### OIDC / Cloud Auth Failures

`Error: Credentials could not be loaded` or `Not authorized to perform sts:AssumeRoleWithWebIdentity`. Usual causes, in order:
1. Missing `permissions: id-token: write` on the job or workflow.
2. The trust policy's subject claim doesn't match — the `sub` for a branch push (`repo:org/repo:ref:refs/heads/main`) differs from a PR, an environment, or a tag. Get the actual claim from the failed run and compare it character-for-character with the trust policy condition.
3. The role's trust policy audience isn't `sts.amazonaws.com` (for AWS).

### Job Cancelled / "lost communication with the server" / Hangs

The runner died: out of memory, or a step hung until the 6-hour job limit. Check memory-hungry steps (test parallelism, container builds); add timeouts per step (`timeout-minutes`) so the next failure points at the culprit step instead of the job boundary.

### Cache Failures

`actions/cache` restore failures are almost never worth debugging as such — the cache is best-effort. If a job *hard-fails* on a cache miss, the job is wrong: it must be able to rebuild from scratch. Fix the job, not the cache.

## Reporting

State clearly: what environmental factor changed or misbehaved, the evidence (image versions, run comparison, log lines), and the fix. Distinguish "closed off this class of drift" (pinned toolchain, cached artifact) from "worked around it once" — prefer the former, and say when you've only achieved the latter.
