# skwashd/skills

A small collection of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills for everyday development work: managing Dependabot config, hardening GitHub Actions workflows, and looking up PyPI package versions.

Each skill lives in its own directory and follows the standard `SKILL.md` format. Claude Code loads these files automatically when a matching task comes up.

> Skills are instructions for coding agents, not documentation for humans. The `SKILL.md` files in this repo are written to be loaded into Claude Code's context. This README is the only file aimed at people.

## What's in the box

### dependabot-manager

Generates and maintains `.github/dependabot.yml` files with a consistent house style: every supported ecosystem listed (commented out when unused), daily schedules, a one-day cooldown floor, and ecosystem-specific labels. Includes a reference table covering 30+ package ecosystems. When editing an existing config, the skill preserves user-defined rules such as `groups`, `ignore`, `allow`, and `registries` rather than rewriting them.

Trigger phrases: "set up Dependabot", "add npm to my dependabot config", "review this dependabot.yml".

### github-actions-security

Applies the GitHub Actions hardening rules used by the Astral team (the maintainers of Ruff and uv). Covers blocked triggers (`pull_request_target`, `workflow_run`), pinning every action to a full commit SHA (with a `gh` lookup procedure), fixing the runner image version, applying minimal `permissions:`, late authentication, deployment-environment isolation for secrets, and a reference `zizmor` CI workflow.

Trigger phrases: "secure this workflow", "review my GitHub Actions", "pin these actions", "harden the release pipeline".

### pypi-version-lookup

Looks up the latest stable version of any Python package from the PyPI JSON API using `curl` and `jq`. Includes retry-with-backoff and batch-lookup patterns. Useful when pinning dependencies in `requirements.txt`, `pyproject.toml`, Dockerfiles, or any CI config.

Trigger phrases: "what's the latest version of requests?", "pin numpy", "update this requirements file".

## Installing

The easiest way to install is the [`skills` CLI from Vercel Labs](https://www.npmjs.com/package/skills), which speaks `owner/repo` shorthand and handles both project-scoped and global installs.

### Install all three skills into the current project

```bash
npx skills add skwashd/skills
```

This drops the skills into `.claude/skills/` in the current directory. Commit that folder if you want every contributor to pick them up.

### Install all three skills globally

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
ln -s ~/src/skwashd-skills/pypi-version-lookup     ~/.claude/skills/pypi-version-lookup
```

Symlinking lets you `git pull` once in `~/src/skwashd-skills` to update every skill.

### Verifying the install

Open Claude Code in a project where the skill should be active and run `/skills`. Each installed skill should appear with its name and description.

## Contributing

New skills are welcome. Before opening a PR, read [`anthropics/skills/skill-creator`](https://github.com/anthropics/skills/tree/main/skills/skill-creator) for the upstream guidance on how to author a `SKILL.md` file. You can run it as a skill itself if you want Claude to scaffold and review your skill against its rules.

## License

[MIT](./LICENSE).
