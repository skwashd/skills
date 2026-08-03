---
name: dependabot-manager
description: >
  Manage GitHub Dependabot configuration files (.github/dependabot.yml). Use this skill whenever the user
  mentions Dependabot, dependabot.yml, dependency version updates, automated dependency PRs, or wants to
  create, update, or review a Dependabot configuration. Also trigger when the user uploads or references
  a dependabot.yml file, asks about supported package ecosystems, or wants to add/remove ecosystems from
  their Dependabot setup. Even if the user just says "set up Dependabot" or "add npm to my dependabot config",
  use this skill.
allowed-tools: Read Write Edit Glob Grep WebFetch
license: MIT
compatibility: >
  No external tooling required. Uses WebFetch against docs.github.com to look up
  unfamiliar Dependabot options. Needs read access to the target repository to
  detect which package ecosystems are actually in use.
metadata:
  author: skwashd
  version: "2.0.0"
---

# Dependabot Manager

Generate and maintain `.github/dependabot.yml` files with standardized settings.

## Core Rules

Every generated `dependabot.yml` **must** follow these rules — no exceptions:

1. **Only ecosystems the repo actually uses.** Detect which package managers are present (see "Detecting Ecosystems in Use" below) and write an entry for each one. Do **not** emit commented-out entries for unused ecosystems — they are noise, they go stale as GitHub adds ecosystems, and re-running this skill is cheaper than maintaining a catalogue in every repo. If the user explicitly asks for an ecosystem you found no evidence for, add it and say so.
2. **Daily schedule.** Every entry uses `schedule.interval: "daily"`.
3. **Three-day cooldown minimum.** Every entry includes a `cooldown` block with at least `default-days: 3`. If the user has set a longer cooldown (e.g., `default-days: 7` or SemVer-specific overrides like `semver-major-days: 14`), **preserve those longer values**. Only add or raise to `3` if missing, set to `0`, or set below `3`.
4. **Language-specific label.** Every entry's `labels` array must contain `"dependencies"` plus the language label from the mapping table below. If the user has additional labels beyond these two, **preserve them**.
5. **Directory defaults to `/`.** If you know or discover the repo is a monorepo, use `directories` with the appropriate paths instead. Note that only the plural `directories` supports globbing — `directory` takes a single literal path.

## Ecosystem Reference Table

Use exactly these `package-ecosystem` YAML values. The "Label" column is the language/platform label to apply.

| Package Manager          | YAML value         | Label            |
|--------------------------|--------------------|------------------|
| Bazel                    | `bazel`            | `bazel`          |
| Bun                      | `bun`              | `javascript`     |
| Bundler (Ruby)           | `bundler`          | `ruby`           |
| Cargo (Rust)             | `cargo`            | `rust`           |
| Composer (PHP)           | `composer`         | `php`            |
| Conda                    | `conda`            | `python`         |
| Deno                     | `deno`             | `javascript`     |
| Dev Containers           | `devcontainers`    | `docker`         |
| Docker                   | `docker`           | `docker`         |
| Docker Compose           | `docker-compose`   | `docker`         |
| .NET SDK                 | `dotnet-sdk`       | `dotnet`         |
| Elm                      | `elm`              | `elm`            |
| Git Submodules           | `gitsubmodule`     | `git`            |
| GitHub Actions           | `github-actions`   | `actions`        |
| Go Modules               | `gomod`            | `go`             |
| Gradle                   | `gradle`           | `java`           |
| Helm Charts              | `helm`             | `helm`           |
| Hex (Elixir)             | `mix`              | `elixir`         |
| Julia                    | `julia`            | `julia`          |
| Maven                    | `maven`            | `java`           |
| Nix flakes               | `nix`              | `nix`            |
| npm / pnpm / Yarn        | `npm`              | `node`           |
| NuGet                    | `nuget`            | `dotnet`         |
| OpenTofu                 | `opentofu`         | `terraform`      |
| pip / pipenv / poetry     | `pip`              | `python`         |
| pre-commit               | `pre-commit`       | `python`         |
| Pub (Dart/Flutter)       | `pub`              | `dart`           |
| Rust Toolchain           | `rust-toolchain`   | `rust`           |
| sbt (Scala)              | `sbt`              | `scala`          |
| Swift                    | `swift`            | `swift`          |
| Terraform                | `terraform`        | `terraform`      |
| uv (Python)              | `uv`               | `python`         |
| vcpkg (C/C++)            | `vcpkg`            | `cpp`            |

**Note:** `npm` covers npm, pnpm, and Yarn. `pip` covers pip, pip-compile, pipenv, and poetry. Only one entry per unique YAML value is needed.

## Template for Each Ecosystem Entry

```yaml
  - package-ecosystem: "<YAML_VALUE>"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 3
    labels:
      - "dependencies"
      - "<LABEL>"
```

## Detecting Ecosystems in Use

Because only ecosystems actually in use get an entry, detection is the first step of every run. Look for these manifest and lockfile markers:

| Ecosystem | Look for |
|---|---|
| `bundler` | `Gemfile`, `Gemfile.lock`, `*.gemspec` |
| `cargo` | `Cargo.toml` |
| `composer` | `composer.json` |
| `conda` | `environment.yml`, `environment.yaml` |
| `deno` | `deno.json`, `deno.jsonc`, `deno.lock` |
| `devcontainers` | `.devcontainer/devcontainer.json`, `.devcontainer.json` |
| `docker` | `Dockerfile`, `Dockerfile.*`, `*.Dockerfile` |
| `docker-compose` | `docker-compose.yml`, `compose.yaml` and variants |
| `dotnet-sdk` | `global.json` |
| `elm` | `elm.json` |
| `github-actions` | any file under `.github/workflows/`, or a top-level `action.yml` |
| `gitsubmodule` | `.gitmodules` |
| `gomod` | `go.mod` |
| `gradle` | `build.gradle`, `build.gradle.kts`, `gradle/libs.versions.toml` |
| `helm` | `Chart.yaml` |
| `julia` | `Project.toml` alongside `Manifest.toml` |
| `maven` | `pom.xml` |
| `mix` | `mix.exs` |
| `nix` | `flake.nix` |
| `npm` | `package.json` |
| `nuget` | `*.csproj`, `*.fsproj`, `*.vbproj`, `packages.config`, `*.sln` |
| `opentofu` | `.tf` files alongside OpenTofu-specific config or lockfile |
| `pip` | `requirements*.txt`, `pyproject.toml`, `Pipfile`, `setup.py`, `setup.cfg` |
| `pre-commit` | `.pre-commit-config.yaml` |
| `pub` | `pubspec.yaml` |
| `rust-toolchain` | `rust-toolchain`, `rust-toolchain.toml` |
| `sbt` | `build.sbt`, `project/build.properties` |
| `swift` | `Package.swift` |
| `terraform` | `*.tf`, `.terraform.lock.hcl` |
| `uv` | `uv.lock`, or `pyproject.toml` with a `[tool.uv]` section |
| `vcpkg` | `vcpkg.json` |
| `bazel` | `MODULE.bazel`, `WORKSPACE`, `WORKSPACE.bazel` |
| `bun` | `bun.lockb`, `bun.lock` |

Two ambiguous cases worth resolving rather than guessing:

- **`pip` vs `uv`.** These are separate Dependabot ecosystems and a project can legitimately need both. If `uv.lock` exists, add `uv`. If there is also a `requirements*.txt` that uv does not manage, add `pip` too. When it's genuinely unclear, ask.
- **`terraform` vs `opentofu`.** Bare `.tf` files alone don't tell you which. Default to `terraform` and ask if the repo shows any OpenTofu-specific signal (`.tofu` files, `tofu` in CI, an OpenTofu-generated lockfile).

If you cannot inspect the repository — the user pasted a config with no surrounding context, say — ask which ecosystems they use rather than guessing or falling back to a full catalogue.

## Workflow

### Creating a New Config

1. Detect which ecosystems the repo uses (see above).
2. Start with `version: 2` and an `updates:` block.
3. Add an entry for each detected ecosystem, plus any the user explicitly asked for.
4. Apply all core rules (daily, cooldown, labels).
5. Output the file to `.github/dependabot.yml`.
6. Tell the user which ecosystems you detected and which you skipped, so they can correct you if the detection missed something.

### Updating an Existing Config

1. Read the existing `dependabot.yml`.
2. **Add** entries for any ecosystems the repo uses that aren't yet configured.
3. **Leave alone** configured ecosystems you found no evidence for — the user may know something the filesystem doesn't. Mention them in the summary rather than deleting them.
4. **Remove** any entries for ecosystems not in the supported table (these may be typos or deprecated values).
5. **Remove `reviewers`.** GitHub removed this option in August 2025; it no longer does anything. Point the user at `CODEOWNERS` as the replacement. This is the one property that gets deleted rather than preserved, so call it out explicitly in the summary. (`assignees` is **not** deprecated — keep it.)
6. **Fix** any entries that violate core rules:
   - Interval not daily → set to daily.
   - Missing cooldown → add `cooldown: { default-days: 3 }`. If cooldown exists but `default-days` is missing, `0`, or below `3`, set it to `3`. If `default-days` is already `>= 3`, keep it. Preserve any SemVer-specific overrides (`semver-major-days`, `semver-minor-days`, `semver-patch-days`) and `include`/`exclude` lists.
   - Missing required labels → **add** `"dependencies"` and the ecosystem's language label. Do **not** remove any extra labels the user has added.
7. **Inform the user** of every change made, in a concise summary. They need awareness, not approval.
8. Preserve any additional valid config the user has (e.g., `ignore`, `allow`, `groups`, `multi-ecosystem-groups`, `registries`, `assignees`, `commit-message`, `open-pull-requests-limit`, etc.).

### Monorepo Detection

If you see evidence of a monorepo (multiple `package.json` files, workspace configs, `lerna.json`, `pnpm-workspace.yaml`, multiple `go.mod` files, etc.), switch from `directory: "/"` to `directories:` with the appropriate paths.

## Short Example

A complete `.github/dependabot.yml` for a repository that uses `npm`, `pip`, and `github-actions` — and nothing else. This is the whole file, not an excerpt: unused ecosystems are simply absent. Every entry follows the template above; substitute the YAML value and label for any other ecosystem from the reference table.

```yaml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 3
    labels:
      - "dependencies"
      - "node"

  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 3
    labels:
      - "dependencies"
      - "python"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 3
    labels:
      - "dependencies"
      - "actions"
```

## Per-Language Example Files

Concrete entries for every supported ecosystem live alongside this skill in the `examples/` directory, grouped by language family. Read the file for the languages your target repo uses, copy the entries you need, and merge them into the user's `dependabot.yml`. **Do not load these files unless you actually need them** — they exist so the SKILL.md stays focused.

| File | Ecosystems covered |
|---|---|
| `examples/javascript.yml` | `npm` (npm/pnpm/Yarn), `bun`, `deno` |
| `examples/python.yml` | `pip` (pip/pipenv/poetry), `uv`, `conda`, `pre-commit` |
| `examples/jvm.yml` | `gradle`, `maven`, `sbt` |
| `examples/dotnet.yml` | `dotnet-sdk`, `nuget` |
| `examples/rust.yml` | `cargo`, `rust-toolchain` |
| `examples/go.yml` | `gomod` |
| `examples/ruby.yml` | `bundler` |
| `examples/php.yml` | `composer` |
| `examples/containers.yml` | `docker`, `docker-compose`, `devcontainers`, `helm` |
| `examples/iac.yml` | `terraform`, `opentofu`, `bazel`, `nix` |
| `examples/github.yml` | `github-actions`, `gitsubmodule` |
| `examples/other.yml` | `mix` (Elixir), `pub` (Dart), `julia`, `elm`, `swift`, `vcpkg` |

## Cooldown and Cadence

These two settings interact, and the interaction is the thing people get wrong.

**Why three days.** GitHub applies a 3-day cooldown to version updates by default now, even when `cooldown` is absent from the config entirely. Writing a shorter value than that produces a config that *looks* stricter than the platform default while actually being weaker than doing nothing. Three days is the floor because it is what you get anyway; setting it explicitly documents the intent and gives you an obvious place to raise it.

**Why daily, despite the cooldown.** The cooldown is measured from each release, not from a fixed point in the week, so a daily schedule is not made redundant by it. On a project that ships several times a week there is always a sliding window of releases coming out of cooldown, and a daily schedule picks each one up the day it becomes eligible. A weekly schedule would batch those into one large PR up to six days late for no security benefit. Daily plus a cooldown gives you both promptness and a vetting window.

**Security updates are never delayed.** `cooldown` applies to *version* updates only. Nothing in this configuration slows a security fix down — that's what makes a conservative version-update cadence safe to adopt.

**Grouping and per-dependency overrides are the user's call.** `groups`, `multi-ecosystem-groups`, `ignore`, and `allow` all depend on how a team wants to triage PRs, and there is no house default worth imposing. Preserve whatever the user has, and suggest grouping only if they say PR volume is a problem.

## Important Notes

- `pre-commit` uses the `python` label because pre-commit is a Python-based tool, even though hooks can be for any language.
- `opentofu` uses the `terraform` label because OpenTofu is a Terraform fork and the community treats them as the same ecosystem.
- `bun` and `deno` both use the `javascript` label; `npm` uses `node`. This is deliberate — `npm` predates the others and its label is well established in existing repos.
- If the user has both `pip` and `uv` entries, that's valid — they are separate ecosystems in Dependabot despite both being Python. Keep both.
- Docker and Docker Compose are separate ecosystems and should each have their own entry.
- `open-pull-requests-limit` defaults to 5 for version updates. Security updates are counted separately.

## Reference Documentation

If you need to look up any Dependabot configuration option (e.g., `registries`, `groups`, `ignore`, `allow`, `versioning-strategy`, etc.), fetch the official options reference:

**https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference**

Use the `WebFetch` tool on this URL whenever you encounter an unfamiliar option or need to verify correct syntax.
