---
name: dependabot-manager
description: >
  Manage GitHub Dependabot configuration files (.github/dependabot.yml). Use this skill whenever the user
  mentions Dependabot, dependabot.yml, dependency version updates, automated dependency PRs, or wants to
  create, update, or review a Dependabot configuration. Also trigger when the user uploads or references
  a dependabot.yml file, asks about supported package ecosystems, or wants to add/remove ecosystems from
  their Dependabot setup. Even if the user just says "set up Dependabot" or "add npm to my dependabot config",
  use this skill.
allowed-tools: Read Write Edit WebFetch
---

# Dependabot Manager

Generate and maintain `.github/dependabot.yml` files with standardized settings.

## Core Rules

Every generated `dependabot.yml` **must** follow these rules — no exceptions:

1. **All supported ecosystems present.** Every ecosystem listed in the reference table below gets an entry. If the user's repo doesn't use an ecosystem, include it commented out with a note so they can enable it later.
2. **Daily schedule.** Every entry uses `schedule.interval: "daily"`.
3. **One-day cooldown minimum.** Every entry includes a `cooldown` block with at least `default-days: 1`. If the user has set a longer cooldown (e.g., `default-days: 3` or SemVer-specific overrides like `semver-major-days: 5`), **preserve those longer values**. Only add or raise to `1` if missing or set to `0`.
4. **Language-specific label.** Every entry's `labels` array must contain `"dependencies"` plus the language label from the mapping table below. If the user has additional labels beyond these two, **preserve them**.
5. **Directory defaults to `/`.** If you know or discover the repo is a monorepo, use `directories` with the appropriate paths instead.

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
| npm / pnpm / Yarn        | `npm`              | `node`           |
| NuGet                    | `nuget`            | `dotnet`         |
| OpenTofu                 | `opentofu`         | `terraform`      |
| pip / pipenv / poetry     | `pip`              | `python`         |
| pre-commit               | `pre-commit`       | `python`         |
| Pub (Dart/Flutter)       | `pub`              | `dart`           |
| Rust Toolchain           | `rust-toolchain`   | `rust`           |
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
      default-days: 1
    labels:
      - "dependencies"
      - "<LABEL>"
```

## Workflow

### Creating a New Config

1. Start with `version: 2` and an `updates:` block.
2. Add an active (uncommented) entry for **every** ecosystem from the table above.
3. If the user specifies which ecosystems they actually use, keep those active and **comment out** the rest with a header like `# Uncomment to enable <name>`.
4. Apply all core rules (daily, cooldown, labels).
5. Output the file to `.github/dependabot.yml`.

### Updating an Existing Config

1. Read the existing `dependabot.yml`.
2. **Add** any ecosystems from the table that are missing (commented out if usage is unknown).
3. **Remove** any entries for ecosystems not in the supported table (these may be typos or deprecated values).
4. **Fix** any entries that violate core rules:
   - Interval not daily → set to daily.
   - Missing cooldown → add `cooldown: { default-days: 1 }`. If cooldown exists but `default-days` is missing or `0`, set it to `1`. If `default-days` is already `>= 1`, keep it. Preserve any SemVer-specific overrides (`semver-major-days`, `semver-minor-days`, `semver-patch-days`) and `include`/`exclude` lists.
   - Missing required labels → **add** `"dependencies"` and the ecosystem's language label. Do **not** remove any extra labels the user has added.
5. **Inform the user** of every change made, in a concise summary. They need awareness, not approval.
6. Preserve any additional valid config the user has (e.g., `ignore`, `allow`, `groups`, `registries`, `assignees`, `reviewers`, `commit-message`, `open-pull-requests-limit`, etc.).

### Monorepo Detection

If you see evidence of a monorepo (multiple `package.json` files, workspace configs, `lerna.json`, `pnpm-workspace.yaml`, multiple `go.mod` files, etc.), switch from `directory: "/"` to `directories:` with the appropriate paths.

## Short Example

A minimal `.github/dependabot.yml` for a repository that uses `npm`, `pip`, and `github-actions`. Every entry follows the template above; substitute the YAML value and label for any other ecosystem from the reference table.

```yaml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 1
    labels:
      - "dependencies"
      - "node"

  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 1
    labels:
      - "dependencies"
      - "python"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 1
    labels:
      - "dependencies"
      - "actions"
```

## Per-Language Example Files

Concrete entries for every supported ecosystem live alongside this skill in the `examples/` directory, grouped by language family. Read the file for the languages your target repo uses, copy the entries you need, and merge them into the user's `dependabot.yml`. **Do not load these files unless you actually need them** — they exist so the SKILL.md stays focused.

| File | Ecosystems covered |
|---|---|
| `examples/javascript.yml` | `npm` (npm/pnpm/Yarn), `bun` |
| `examples/python.yml` | `pip` (pip/pipenv/poetry), `uv`, `conda`, `pre-commit` |
| `examples/jvm.yml` | `gradle`, `maven` |
| `examples/dotnet.yml` | `dotnet-sdk`, `nuget` |
| `examples/rust.yml` | `cargo`, `rust-toolchain` |
| `examples/go.yml` | `gomod` |
| `examples/ruby.yml` | `bundler` |
| `examples/php.yml` | `composer` |
| `examples/containers.yml` | `docker`, `docker-compose`, `devcontainers`, `helm` |
| `examples/iac.yml` | `terraform`, `opentofu`, `bazel` |
| `examples/github.yml` | `github-actions`, `gitsubmodule` |
| `examples/other.yml` | `mix` (Elixir), `pub` (Dart), `julia`, `elm`, `swift`, `vcpkg` |

## Important Notes

- The `cooldown` option only applies to **version updates**, not security updates. This is by design — security updates should never be delayed.
- `pre-commit` uses the `python` label because pre-commit is a Python-based tool, even though hooks can be for any language.
- `opentofu` uses the `terraform` label because OpenTofu is a Terraform fork and the community treats them as the same ecosystem.
- If the user has both `pip` and `uv` entries, that's valid — they are separate ecosystems in Dependabot despite both being Python. Keep both.
- Docker and Docker Compose are separate ecosystems and should each have their own entry.

## Reference Documentation

If you need to look up any Dependabot configuration option (e.g., `registries`, `groups`, `ignore`, `allow`, `versioning-strategy`, etc.), fetch the official options reference:

**https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference**

Use the `WebFetch` tool on this URL whenever you encounter an unfamiliar option or need to verify correct syntax.
