# skwashd/skills

A small collection of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills for everyday development work, with a few borrowed from elsewhere.

Each skill lives in its own directory and follows the standard `SKILL.md` format. Claude Code loads these files automatically when a matching task comes up.

> Skills are instructions for coding agents, not documentation for humans. The `SKILL.md` files in this repo are written to be loaded into Claude Code's context. This README is the only file aimed at people.

## Layout

```
.                        skills written here, one directory each
├── .external/           upstream repos, as git submodules
│   └── <owner>-<repo>/
├── .private/            personal or client skills, gitignored
├── handoff -> .external/…    symlink to a skill inside a submodule
└── simple-english -> .external/…
```

Every installable skill is at the top level. Some are real directories. Others are symlinks into `.external/`. The install commands are the same for all of them. If you clone this repo as `~/.claude/skills`, that top level is your skills directory.

## What's in the box

### aws-step-functions-jsonata

Writes, validates, tests and deploys AWS Step Functions state machines in **JSONata** QueryLanguage mode. The skill never emits JSONPath. If you give it a JSONPath state machine, it ports the machine first.

The work runs in five phases:

1. **Capture intent** — the trigger, the input and output shapes, Standard or Express, and the error policy for each external call.
2. **Draw the graph** — a YAML outline of the states, before any ASL.
3. **Fill the ASL** — from one of eight canonical templates.
4. **Validate** — a hard gate, described below.
5. **Deploy** — deployment scaffolding, but only when you ask for it.

The validator is `scripts/validate.py`. It needs Python 3 and no other packages. It runs four layers:

| Layer | What it does | Needs credentials |
| --- | --- | --- |
| L1 | JSON Schema, JSONata only | no |
| L2 | Graph reachability, JSONata syntax, `$states` scope, IAM inference | no |
| L3 | `aws stepfunctions validate-state-machine-definition` | yes |
| L4 | `aws stepfunctions test-state` per state, with mocks | yes, and the `--test-states` flag |

L1 and L2 are mandatory. If there are no AWS credentials, the validator skips L3 and L4 and prints a banner. The exit code separates four results: clean, errors, warnings only, and clean-but-skipped.

The skill has one strong opinion. A common error-handling state is an anti-pattern. If every `Catch` routes to one `HandleError` state, three things break. Redrive from the failed state becomes impossible. The diagnostic context loses its anchor in the execution history. The execution reports as succeeded, so EventBridge does not alert on it.

The skill handles known, recoverable errors on the state that produced them. It lets unknown errors fail the execution at the state where they occurred.

Deployment emitters cover Terraform, SAM, CDK, CloudFormation and the plain AWS CLI. Each emitter writes the IaC file and an execution-role policy. It infers that policy from the Task `Resource` ARNs. `render_mermaid.py` draws the workflow as a diagram for review.

Trigger phrases: "orchestrate these Lambdas", "wire up this pipeline", "review my state machine", "convert this to JSONata", or sharing an `.asl.json` file.

### dependabot-manager

Generates and maintains `.github/dependabot.yml` files with a consistent house style: an entry for every ecosystem the repo actually uses, daily schedules, a three-day cooldown floor, and ecosystem-specific labels. Includes a reference table covering 30+ package ecosystems, plus a detection table mapping each one to the manifest files that indicate it is in use. When editing an existing config, the skill preserves user-defined rules such as `groups`, `ignore`, `allow`, and `registries` rather than rewriting them. The skill strips `reviewers`, which GitHub removed in 2025.

Trigger phrases: "set up Dependabot", "add npm to my dependabot config", "review this dependabot.yml".

### github-actions-security

Applies the GitHub Actions hardening rules used by the Astral team (the maintainers of Ruff and uv). Covers blocked triggers (`pull_request_target`, `workflow_run`), pinning every action to a full commit SHA (with a `gh` lookup procedure), `actions/checkout`'s pwn-request protections and the `allow-unsafe-pr-checkout` red flag, fixing the runner image version, applying minimal `permissions:`, late authentication, deployment-environment isolation for secrets, a reference `zizmor` CI workflow, and case studies of the 2026 Trivy and `actions-cool` supply-chain compromises.

Trigger phrases: "secure this workflow", "review my GitHub Actions", "pin these actions", "harden the release pipeline".

### jira-acli

Reads, creates and updates Jira work items through [`acli`](https://developer.atlassian.com/cloud/acli/), Atlassian's official CLI. Its premise is that acli's custom-field handling is under-documented and site-specific, so every workflow starts by asking the live instance what it expects and ends by reading back what was actually written.

The parts that are hard to work out from the docs alone: custom fields can only be set at **create** time, via an `additionalAttributes` object in a `--from-json` payload — `edit` rejects them outright ([CLOUD-12876](https://jira.atlassian.com/browse/CLOUD-12876)); acli has no way to *list* fields, so discovery goes through `workitem view --fields "*all" --json` against an already-populated item; and rich-text fields need a full ADF document rather than a string. Includes a validated ADF subset with the traps that catch Markdown conversion.

Trigger phrases: "pull in DAVE-123", "break this epic into stories", "push these to Jira", "what does this ticket say?".

### pypi-version-lookup

Looks up the latest stable version of any Python package from the PyPI JSON API using `curl` and `jq`. Documents exactly what `info.version` does and does not guarantee, the pipeline-exit-status trap that makes failed lookups look successful, yanked-release and fresh-release cooldown checks, and PEP 792 project status (including quarantined packages). Ships a batch lookup script that runs under `uv run --script` with no third-party dependencies. Useful when pinning dependencies in `requirements.txt`, `pyproject.toml`, Dockerfiles, or any CI config.

Trigger phrases: "what's the latest version of requests?", "pin numpy", "update this requirements file".

### ship-story

Takes one story from ticket to verified deployment: read the ticket, branch, implement, open a PR, watch CI, diagnose failures from their logs, merge, confirm the deploy, and verify the deployed behaviour against the acceptance criteria before closing.

The organising idea is that a story is done when you have **observed** the acceptance criteria being met — not when the code is written, not when CI is green. Most of the skill is about not finishing early.

Assumes `git`, `gh`, `acli`, the AWS CLI and Playwright are available, and reads the project's own lint/test/build commands from its `CLAUDE.md` rather than hardcoding a toolchain.

> **Note:** depends on `jira-acli` for the ticket-reading and ticket-closing steps. Install both, or the first and last steps will not work.

Trigger phrases: "implement DAVE-123", "pick up this story", "ship this ticket".

### terraform-review

Reviews and generates Terraform (and OpenTofu) with checks aligned to tflint's AWS ruleset and the [`dave-says`](https://github.com/skwashd/tflint-ruleset-dave-says) custom ruleset. Covers resource naming, file organisation, IAM policy structure, S3 account regional namespaces, CloudWatch retention, VPC and security group patterns, module design, keeping secrets out of state with write-only arguments, and a fmt → validate → tflint → test workflow. Findings are grouped by severity and cite the tflint rule name where one exists, so the user knows which checks are automatable.

Bundles a starter `.tflint.hcl` and a `validate.sh` runner.

> **Note:** the full experience needs [`tflint-ruleset-dave-says`](https://github.com/skwashd/tflint-ruleset-dave-says), which `tflint --init` downloads from the config in `assets/.tflint.hcl`. Without it the skill still applies its guidance by reading the `.tf` files directly — you just lose the automated checks and `--fix` support.

Trigger phrases: "review my Terraform", "here's my Terraform, thoughts?", "clean up my infra code", or simply sharing a `.tf` file.

## External skills

Not every useful skill is worth a rewrite. When someone else has done the work, this repo uses their skill instead of a fork.

The mechanism has two parts:

1. The upstream repository sits under `.external/<owner>-<repo>/` as a git submodule, pinned to one commit.
2. A symlink at the top level points to the one skill directory inside that repository.

Three things are committed here: the `.gitmodules` entry, the pinned commit, and the symlink. The upstream files stay upstream. There are no copies to update and no diffs to reconcile. `git log` in `.external/<repo>` shows their history and does not pollute this one. The symlink makes the skill installable, because it puts the skill where every other skill lives.

### Catalogue

| Skill | Upstream | Path in upstream | What it does |
| --- | --- | --- | --- |
| `handoff` | [mattpocock/skills](https://github.com/mattpocock/skills) | `skills/productivity/handoff` | Compacts the current conversation into a handoff document, so that a fresh agent can continue the work. The document goes to the temporary directory of the OS, not the workspace. It points to existing specs, plans and commits by path, and it redacts secrets and personal data. It also names the skills that the next session must load. The frontmatter sets `disable-model-invocation: true`, so the skill runs only when you name it. It takes an optional argument that describes the next session. |
| `simple-english` | [AminBlg/SimpleEnglish](https://github.com/AminBlg/SimpleEnglish) | `skills/simple-english` | Writes and rewrites technical text under [ASD-STE100](https://www.asd-ste100.org/) Simplified Technical English. STE is the controlled language that aerospace has used for maintenance manuals since 1983. The skill applies the 53 rules of the standard: 20/25-word sentence limits, one word one meaning, simple tenses, active voice, and condition before command. It classifies each passage as procedural or descriptive first, because every other rule depends on that. It removes AI slop as a side effect. It has a pragmatic mode and a strict mode. |

### Cloning and updating

```bash
# First clone — submodules included
git clone --recurse-submodules git@github.com:skwashd/skills.git

# Already cloned without them
git submodule update --init --recursive

# Pull upstream changes and pin the new commits
git submodule update --remote
git add .external && git commit -m "Bump external skills"
```

If `handoff` or `simple-english` are broken symlinks, git did not check out the submodules. Run the `--init` command above.

### Adding another one

```bash
git submodule add git@github.com:<owner>/<repo>.git .external/<owner>-<repo>
ln -s .external/<owner>-<repo>/skills/<skill-name> <skill-name>
git add .gitmodules .external/<owner>-<repo> <skill-name>
```

Read the upstream licence before you add the submodule. Then add a row to the catalogue above. The symlink name must match the `name:` field of the skill, because Claude Code matches on the directory name.

## Private skills

Some skills are client-specific. Some contain internal hostnames or process detail. Some are not ready to publish. These skills live in `.private/`. Git ignores the whole directory. Only `.gitkeep` is tracked, so the directory exists in a fresh clone, and the contents stay on your machine.

There are two ways to use it.

**Write the skill in place:**

```bash
mkdir -p .private/acme-deploy
$EDITOR .private/acme-deploy/SKILL.md
```

**Or create a symlink to a private repo**, so that the skill stays under version control with the right access rules:

```bash
ln -s ~/src/acme-internal-skills/deploy .private/acme-deploy
```

The ignore rule covers both methods. An accidental `git add -A` cannot commit these skills.

### Making private skills live

`.private/` works like `.external/`. The content lives in a directory that Claude Code skips, and a top-level symlink makes the skill live. Use this pattern for other people's skills too, and for anything else that must stay out of the history of this repo.

Run this from the root of the repository:

```bash
ln -s .private/acme-deploy acme-deploy
```

To link every private skill at the same time, run this loop:

```bash
for skill in .private/*/; do
  ln -sfn "${skill%/}" "$(basename "$skill")"
done
```

Run the loop again after you add a skill. The `-f` flag replaces a stale link. The `-n` flag stops `ln` from writing inside a directory that is already a symlink. Git shows each new symlink as untracked. If you want a clean `git status`, add the name of the symlink to `.gitignore`.

If you cloned the repository somewhere other than `~/.claude/skills`, create the symlink in your skills directory instead:

```bash
ln -s ~/src/skwashd-skills/.private/acme-deploy ~/.claude/skills/acme-deploy
```

## Installing

The easiest way to install the public skills is the [`skills` CLI from Vercel Labs](https://www.npmjs.com/package/skills), which speaks `owner/repo` shorthand and handles both project-scoped and global installs.

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

> `handoff` and `simple-english` are symlinks into submodules, not real directories. The CLI can fail to resolve them. If the CLI does not install them, install them from their upstream repositories, or use the clone method below.

### Clone into your skills directory

```bash
git clone --recurse-submodules git@github.com:skwashd/skills.git ~/.claude/skills
```

The repository becomes your personal skills directory. Every top-level directory is a skill, so Claude Code finds all of them at once. `.external/` and `.private/` start with a dot, so Claude Code skips them. `handoff` and `simple-english` are symlinks into `.external/`, and they resolve as normal skill directories. To update every skill, run `git pull` in `~/.claude/skills`.

If the skills belong to one project only, clone into the `.claude/skills/` directory of that project instead.

If `~/.claude/skills` already exists and holds other skills, git refuses to clone into it. Move those skills into `.private/`, then link them back:

```bash
mv ~/.claude/skills ~/.claude/skills.old
git clone --recurse-submodules git@github.com:skwashd/skills.git ~/.claude/skills
mv ~/.claude/skills.old/* ~/.claude/skills/.private/
```

The [Private skills](#private-skills) section above covers the symlinks that make those skills live again.

### Verifying the install

Open Claude Code in a project where the skill should be active and run `/skills`. Each installed skill should appear with its name and description.

## Evals

Most skills ship an `evals/` directory containing test cases: a realistic user prompt, any input files it needs, and assertions describing what a good response contains. They cover both positive coverage ("flags X") and false positives ("does NOT flag Y" on already-good input).

```
<skill>/evals/
├── evals.json       # prompts + assertions
├── inputs/          # fixture files, where the eval needs them
└── README.md        # what each case tests, and how to run them
```

Three skills have no evals yet. A test of `jira-acli` or `ship-story` needs a live Jira site and a real pipeline, so those cases need a design first. `aws-step-functions-jsonata` uses its own validator instead, because its output is machine-checkable. The validator already enforces most of what an eval can assert. Cases for the design decisions are still useful: the choice between Standard and Express, and the shape of the error handling.

External skills bring the evals of their upstream repository. `simple-english` has benchmark results in `.external/AminBlg-SimpleEnglish/evals/`.

The [`skill-creator`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) plugin can run these, including with/without-skill benchmarking and description tuning:

```
/plugin install skill-creator@claude-plugins-official
```

For an informal pass, run each prompt in a fresh session with the skill in scope and check the output against the assertions by hand.

## Contributing

New skills are welcome. Before opening a PR, read [`anthropics/skills/skill-creator`](https://github.com/anthropics/skills/tree/main/skills/skill-creator) for the upstream guidance on how to author a `SKILL.md` file. You can run it as a skill itself if you want Claude to scaffold and review your skill against its rules.

If you are adding or changing a skill, please add or update its evals in the same commit where the skill is testable without live credentials.

Recommendations for skills in other repositories are also welcome. Open an issue instead of a pull request, because a new external skill needs a new submodule.

## License

[MIT](./LICENSE). External skills under `.external/` keep their own licences.
