# skwashd/skills

A small collection of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills for everyday development work.

Each skill lives in its own directory and follows the standard `SKILL.md` format. Claude Code loads these files automatically when a matching task comes up.

> Skills are instructions for coding agents, not documentation for humans. The `SKILL.md` files in this repo are written to be loaded into Claude Code's context. This README is the only file aimed at people.

## What's in the box

### dependabot-manager

Generates and maintains `.github/dependabot.yml` files with a consistent house style: an entry for every ecosystem the repo actually uses, daily schedules, a three-day cooldown floor, and ecosystem-specific labels. Includes a reference table covering 30+ package ecosystems, plus a detection table mapping each one to the manifest files that indicate it is in use. When editing an existing config, the skill preserves user-defined rules such as `groups`, `ignore`, `allow`, and `registries` rather than rewriting them. The skill strips `reviewers`, which GitHub removed in 2025.

Trigger phrases: "set up Dependabot", "add npm to my dependabot config", "review this dependabot.yml".

### github-actions-security

Applies the GitHub Actions hardening rules used by the Astral team (the maintainers of Ruff and uv). Covers blocked triggers (`pull_request_target`, `workflow_run`), pinning every action to a full commit SHA (with a `gh` lookup procedure), `actions/checkout`'s pwn-request protections and the `allow-unsafe-pr-checkout` red flag, fixing the runner image version, applying minimal `permissions:`, late authentication, deployment-environment isolation for secrets, a reference `zizmor` CI workflow, and case studies of the 2026 Trivy and `actions-cool` supply-chain compromises.

Trigger phrases: "secure this workflow", "review my GitHub Actions", "pin these actions", "harden the release pipeline".

### pypi-version-lookup

Looks up the latest stable version of any Python package from the PyPI JSON API using `curl` and `jq`. Documents exactly what `info.version` does and does not guarantee, the pipeline-exit-status trap that makes failed lookups look successful, yanked-release and fresh-release cooldown checks, and PEP 792 project status (including quarantined packages). Ships a batch lookup script that runs under `uv run --script` with no third-party dependencies. Useful when pinning dependencies in `requirements.txt`, `pyproject.toml`, Dockerfiles, or any CI config.

Trigger phrases: "what's the latest version of requests?", "pin numpy", "update this requirements file".

### terraform-review

Reviews and generates Terraform (and OpenTofu) with checks aligned to tflint's AWS ruleset and the [`dave-says`](https://github.com/skwashd/tflint-ruleset-dave-says) custom ruleset. Covers resource naming, file organisation, IAM policy structure, S3 account regional namespaces, CloudWatch retention, VPC and security group patterns, module design, keeping secrets out of state with write-only arguments, and a fmt → validate → tflint → test workflow. Findings are grouped by severity and cite the tflint rule name where one exists, so the user knows which checks are automatable.

Bundles a starter `.tflint.hcl` and a `validate.sh` runner.

> **Note:** the full experience needs [`tflint-ruleset-dave-says`](https://github.com/skwashd/tflint-ruleset-dave-says), which `tflint --init` downloads from the config in `assets/.tflint.hcl`. Without it the skill still applies its guidance by reading the `.tf` files directly — you just lose the automated checks and `--fix` support.

Trigger phrases: "review my Terraform", "here's my Terraform, thoughts?", "clean up my infra code", or simply sharing a `.tf` file.

### jira-acli

Reads, creates and updates Jira work items through [`acli`](https://developer.atlassian.com/cloud/acli/), Atlassian's official CLI. Its premise is that acli's custom-field handling is under-documented and site-specific, so every workflow starts by asking the live instance what it expects and ends by reading back what was actually written.

The parts that are hard to work out from the docs alone: custom fields can only be set at **create** time, via an `additionalAttributes` object in a `--from-json` payload — `edit` rejects them outright ([CLOUD-12876](https://jira.atlassian.com/browse/CLOUD-12876)); acli has no way to *list* fields, so discovery goes through `workitem view --fields "*all" --json` against an already-populated item; and rich-text fields need a full ADF document rather than a string. Includes a validated ADF subset with the traps that catch Markdown conversion.

Trigger phrases: "pull in DAVE-123", "break this epic into stories", "push these to Jira", "what does this ticket say?".

### ship-story

Takes one story from ticket to verified deployment: read the ticket, branch, implement, open a PR, watch CI, diagnose failures from their logs, merge, confirm the deploy, and verify the deployed behaviour against the acceptance criteria before closing.

The organising idea is that a story is done when you have **observed** the acceptance criteria being met — not when the code is written, not when CI is green. Most of the skill is about not finishing early.

Assumes `git`, `gh`, `acli`, the AWS CLI and Playwright are available, and reads the project's own lint/test/build commands from its `CLAUDE.md` rather than hardcoding a toolchain.

> **Note:** depends on `jira-acli` for the ticket-reading and ticket-closing steps. Install both, or the first and last steps will not work.

Trigger phrases: "implement DAVE-123", "pick up this story", "ship this ticket".

## Installing

The easiest way to install is the [`skills` CLI from Vercel Labs](https://www.npmjs.com/package/skills), which speaks `owner/repo` shorthand and handles both project-scoped and global installs.

### Install every skill into the current project

```bash
npx skills add skwashd/skills
```

This drops the skills into `.claude/skills/` in the current directory. Commit that folder if you want every contributor to pick them up.

### Install every skill globally

```bash
npx skills add skwashd/skills -g
```

The `-g` flag installs into `~/.claude/skills/`, making the skills available in every project on your machine.

### Install just one skill

```bash
npx skills add skwashd/skills --skill github-actions-security
```

Combine with `-g` for a global single-skill install. Run with `--list` first to see what's available:

```bash
npx skills add skwashd/skills --list
```

### Manual install (if you'd rather not use npx)

```bash
git clone https://github.com/skwashd/skills.git ~/src/skwashd-skills
mkdir -p ~/.claude/skills
ln -s ~/src/skwashd-skills/dependabot-manager      ~/.claude/skills/dependabot-manager
ln -s ~/src/skwashd-skills/github-actions-security ~/.claude/skills/github-actions-security
ln -s ~/src/skwashd-skills/jira-acli               ~/.claude/skills/jira-acli
ln -s ~/src/skwashd-skills/pypi-version-lookup     ~/.claude/skills/pypi-version-lookup
ln -s ~/src/skwashd-skills/ship-story              ~/.claude/skills/ship-story
ln -s ~/src/skwashd-skills/terraform-review        ~/.claude/skills/terraform-review
```

Symlinking lets you `git pull` once in `~/src/skwashd-skills` to update every skill.

### Verifying the install

Open Claude Code in a project where the skill should be active and run `/skills`. Each installed skill should appear with its name and description.

## Evals

Most skills ship an `evals/` directory containing test cases: a realistic user prompt, any input files it needs, and assertions describing what a good response contains. They cover both positive coverage ("flags X") and false positives ("does NOT flag Y" on already-good input).

`jira-acli` and `ship-story` do not have evals yet — both are hard to test without a live Jira site and a real pipeline, so their cases need designing rather than just writing.

```
<skill>/evals/
├── evals.json       # prompts + assertions
├── inputs/          # fixture files, where the eval needs them
└── README.md        # what each case tests, and how to run them
```

The [`skill-creator`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) plugin can run these, including with/without-skill benchmarking and description tuning:

```
/plugin install skill-creator@claude-plugins-official
```

For an informal pass, run each prompt in a fresh session with the skill in scope and check the output against the assertions by hand.

## Contributing

New skills are welcome. Before opening a PR, read [`anthropics/skills/skill-creator`](https://github.com/anthropics/skills/tree/main/skills/skill-creator) for the upstream guidance on how to author a `SKILL.md` file. You can run it as a skill itself if you want Claude to scaffold and review your skill against its rules.

If you are adding or changing a skill, please add or update its evals in the same commit where the skill is testable without live credentials.

## License

[MIT](./LICENSE).
