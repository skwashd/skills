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
├── aws-iam -> .external/…    AWS symlinks you create yourself, gitignored
├── grilling -> .external/…   committed symlinks to skills inside submodules
├── handoff -> .external/…
├── playwright-cli -> .external/…
├── simple-english -> .external/…
└── skill-creator -> .external/…
```

Every installable skill is at the top level. Some are real directories. Others are symlinks into `.external/`. Symlinks that match `aws*` are the exception: you create them, and git ignores them (see [AWS skills](#aws-skills)). The install commands are the same for all of them. If you clone this repo as `~/.claude/skills`, that top level is your skills directory.

## What's in the box

Most of these skills are written here. The rest come from other authors and join through symlinks, so one install gives you all of them. The [External skills](#external-skills) section explains the wiring.

### ci-failure-triage

Takes a failing CI run from "here's the URL/log" to a verified green build. Evidence comes first: the full log of the failing step, fetched with `gh` rather than scraped from the web, and run/job IDs extracted straight from pasted URLs. The failure is then classified — code regression, runner/environment drift, upstream release breakage, deploy-step failure, or flaky — because each class has a different fix strategy. A reference file carries the runner-environment playbooks: image and toolchain drift, shared-IP rate limiting, disk exhaustion, arm64, OIDC, and cache trouble.

The skill never fixes by weakening the checks: no unpinning versions, no suppressing linter findings, no deleting tests, no blanket retries. Deploy-step failures on AWS hand over to [`cloud-aws-failure-triage`](#cloud-aws-failure-triage), and workflow edits get a `zizmor` pass with a pointer to [`github-actions-security`](#github-actions-security) for deeper hardening.

Trigger phrases: "CI is failing", "why did this job fail?", a `github.com/…/actions/runs/…` URL, or a pasted CI log — including Bitbucket Pipelines and other systems.

### cloud-aws-failure-triage

Evidence-first debugging of AWS deploy and runtime failures: CloudFormation/CDK deploy errors (`CREATE_FAILED`, `DELETE_FAILED`, rollbacks, "no changes"), IAM AccessDenied, EventBridge events that never arrive, and Lambda `Runtime.ImportModuleError`. The pasted error carries most of the diagnosis; the skill reads it precisely, gathers the missing facts with read-only calls — or hands the user the exact commands when there are no credentials — and keeps a hypothesis log so failed fixes are never retried in variation. Stateful resources are protected: deleting a stack, table, bucket or user pool is never a debugging step.

Three playbook references cover CloudFormation/CDK, IAM AccessDenied (the error-message anatomy plus classic traps like SSM's two-ARN-form requirement), and EventBridge (the producer → bus → rule → target walk). Fixes land in the Terraform or CDK code, least privilege always — never `"Action": "*"`.

The directory name avoids the `aws` prefix because of this repo's ignore rule (see [AWS skills](#aws-skills)); the skill's registered name is `aws-failure-triage`.

Trigger phrases: a pasted AWS error, "the deploy failed", "AccessDenied", "my Step Function never fired", "fix this IAM policy".

### dependabot-manager

Generates and maintains `.github/dependabot.yml` files with a consistent house style: an entry for every ecosystem the repo actually uses, daily schedules, a three-day cooldown floor, and ecosystem-specific labels. Includes a reference table covering 30+ package ecosystems, plus a detection table mapping each one to the manifest files that indicate it is in use. When editing an existing config, the skill preserves user-defined rules such as `groups`, `ignore`, `allow`, and `registries` rather than rewriting them. The skill strips `reviewers`, which GitHub removed in 2025.

Trigger phrases: "set up Dependabot", "add npm to my dependabot config", "review this dependabot.yml".

### doc-hygiene

Keeps a repository's documentation split cleanly between audiences: README.md for humans, CLAUDE.md/AGENTS.md for coding agents, and never the same content in both — the agent doc references the README rather than restating it, so the copies can't drift apart. Generated regions (terraform-docs and friends) are never hand-edited. A drift check maps what a code change touched — commands, flags, environment variables, enumerations — against what the docs mention, and answers explicitly: either "docs updated" or "no doc changes needed because…".

Bundles a writing-tropes reference that bans the recognisable AI-slop register from all prose, which matters most for READMEs. Also captures hard-won session lessons into the nearest CLAUDE.md so they never have to be relearned.

Trigger phrases: "create a README", "does any documentation need updating?", "the docs are stale", "why does CLAUDE.md duplicate the README?".

### github-actions-security

Applies the GitHub Actions hardening rules used by the Astral team (the maintainers of Ruff and uv). Covers blocked triggers (`pull_request_target`, `workflow_run`), pinning every action to a full commit SHA (with a `gh` lookup procedure), `actions/checkout`'s pwn-request protections and the `allow-unsafe-pr-checkout` red flag, fixing the runner image version, applying minimal `permissions:`, late authentication, deployment-environment isolation for secrets, a reference `zizmor` CI workflow, and case studies of the 2026 Trivy and `actions-cool` supply-chain compromises.

Trigger phrases: "secure this workflow", "review my GitHub Actions", "pin these actions", "harden the release pipeline".

### grilling

By [@mattpocock](https://github.com/mattpocock), symlinked from [mattpocock/skills](https://github.com/mattpocock/skills).

Interviews you about a plan, decision, or idea until you reach a shared understanding. The skill maps the decisions as a tree, then asks questions in rounds. Each round covers the frontier: every question whose prerequisites are settled. Each question comes with a recommended answer.

The skill finds facts itself, through sub-agents. You supply only the decisions. The session ends when nothing is left silently assumed.

Trigger phrases: anything with "grill", or "stress-test my thinking".

### handoff

By [@mattpocock](https://github.com/mattpocock), symlinked from [mattpocock/skills](https://github.com/mattpocock/skills).

Compacts the current conversation into a handoff document, so that a fresh agent can continue the work. The document goes to the temporary directory of the OS, not the workspace. It points to existing specs, plans and commits by path, and it redacts secrets and personal data. It also names the skills that the next session must load.

The frontmatter sets `disable-model-invocation: true`, so the skill runs only when you name it. It takes an optional argument that describes the next session.

### jira-acli

Reads, creates, updates, comments on and transitions Jira work items through [`acli`](https://developer.atlassian.com/cloud/acli/), Atlassian's official CLI. Its premise is that acli's custom-field handling is under-documented and site-specific, so every workflow starts by asking the live instance what it expects and ends by reading back what was actually written.

The parts that are hard to work out from the docs alone: custom fields can only be set at **create** time, via an `additionalAttributes` object in a `--from-json` payload — `edit` rejects them outright ([CLOUD-12876](https://jira.atlassian.com/browse/CLOUD-12876)); acli has no way to *list* fields, so discovery goes through `workitem view --fields "*all" --json` against an already-populated item; and rich-text fields need a full ADF document rather than a string. Includes a validated ADF subset with the traps that catch Markdown conversion.

Trigger phrases: "pull in DAVE-123", "break this epic into stories", "push these to Jira", "what does this ticket say?".

### linear-cli

Reads, creates and updates Linear issues through [`linear`](https://github.com/schpet/linear-cli), a third-party CLI for Linear. Simpler than the Jira equivalent — descriptions are plain markdown and there's no custom-field discovery problem — but labels, projects, milestones, cycles and workflow states are all workspace- or team-specific, so the skill lists before it assumes a name exists.

The CLI path; the Linear MCP server is the equivalent for chat and Cowork sessions where a local CLI isn't available.

Trigger phrases: "pull in ENG-45", "break this project into issues", "push these to Linear", "what does this issue say?".

### playwright-cli

By [@microsoft](https://github.com/microsoft), symlinked from [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli).

Drives a browser through `playwright-cli`, the command-line companion to Playwright. The skill lists the commands for navigation, forms, tabs, storage, network mocking, traces, video, and screenshots. Each command returns an accessibility snapshot, and later commands target elements through refs from that snapshot. The agent works from text, not pixels.

Reference files cover Playwright tests, test generation, request mocking, and session management.

Trigger phrases: "open this page in a browser", "test this form", "automate this web workflow".

### pypi-version-lookup

Looks up the latest stable version of any Python package from the PyPI JSON API using `curl` and `jq`. Documents exactly what `info.version` does and does not guarantee, the pipeline-exit-status trap that makes failed lookups look successful, yanked-release and fresh-release cooldown checks, and PEP 792 project status (including quarantined packages). Ships a batch lookup script that runs under `uv run --script` with no third-party dependencies. Useful when pinning dependencies in `requirements.txt`, `pyproject.toml`, Dockerfiles, or any CI config.

Trigger phrases: "what's the latest version of requests?", "pin numpy", "update this requirements file".

### ship-story

Takes one story from ticket to verified deployment, on Jira, Linear or GitHub Issues: read the ticket, branch, implement, open a PR, watch CI, diagnose failures from their logs, merge, confirm the deploy, and verify the deployed behaviour against the acceptance criteria before closing.

The organising idea is that a story is done when you have **observed** the acceptance criteria being met — not when the code is written, not when CI is green. Most of the skill is about not finishing early.

The workflow itself doesn't change per tracker; only the two ends do. Tracker-specific conventions live in bundled adapter files under `references/`, read once detection settles which tracker applies — never guessed from the work item key's shape, since `PROJ-123` is valid on both Jira and Linear. The deployment platform follows the same pattern: the verification steps are generic, and the AWS commands (with their traps, like `sqs receive-message` not being read-only) live in a reference read only when the project deploys there. Assumes `git` and `gh` always; the tracker's own CLI as applicable; browser automation is used when the session has it, without naming which. Project lint/test/build commands are read from the repository's `CLAUDE.md` rather than hardcoded.

> **Note:** the Jira path depends on `jira-acli` for reading and closing tickets. The Linear path can use `linear-cli` for anything beyond the ship-time commands, which the adapter covers on its own. GitHub Issues needs nothing beyond `gh`.

Trigger phrases: "implement DAVE-123", "pick up this story", "ship this ticket", "ship ENG-45", "close out issue #123".

### simple-english

By [@AminBlg](https://github.com/AminBlg), symlinked from [AminBlg/SimpleEnglish](https://github.com/AminBlg/SimpleEnglish).

Writes and rewrites technical text under [ASD-STE100](https://www.asd-ste100.org/) Simplified Technical English. STE is the controlled language that aerospace has used for maintenance manuals since 1983. The skill applies the 53 rules of the standard: 20/25-word sentence limits, one word one meaning, simple tenses, active voice, and condition before command.

It classifies each passage as procedural or descriptive first, because every other rule depends on that. It removes AI slop as a side effect. It has a pragmatic mode and a strict mode.

Trigger phrases: "make this readable", "de-slop this", "STE", "write for non-native readers".

### skill-creator

By [@anthropics](https://github.com/anthropics), symlinked from [anthropics/skills](https://github.com/anthropics/skills).

Anthropic's own skill. It creates new skills and improves existing ones. It interviews you about intent, then writes a draft. It runs each test prompt twice: once with the skill and once without it. A browser viewer shows every output for your review, next to the benchmark numbers.

A separate loop optimises the description, because the description controls when the skill triggers. The [Contributing](#contributing) section below relies on it.

Trigger phrases: "create a skill", "improve this skill", "run the evals for this skill".

### step-functions-jsonata

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

The [What's in the box](#whats-in-the-box) section describes each skill and credits its author. This table records the wiring only:

| Skill | Upstream | Path in upstream |
| --- | --- | --- |
| `grilling` | [mattpocock/skills](https://github.com/mattpocock/skills) | `skills/productivity/grilling` |
| `handoff` | [mattpocock/skills](https://github.com/mattpocock/skills) | `skills/productivity/handoff` |
| `playwright-cli` | [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli) | `skills/playwright-cli` |
| `simple-english` | [AminBlg/SimpleEnglish](https://github.com/AminBlg/SimpleEnglish) | `skills/simple-english` |
| `skill-creator` | [anthropics/skills](https://github.com/anthropics/skills) | `skills/skill-creator` |

### AWS skills

AWS ([@aws](https://github.com/aws)) publishes skills for its own services in [aws/agent-toolkit-for-aws](https://github.com/aws/agent-toolkit-for-aws). This repo pins the toolkit as a submodule at `.external/aws-agent-toolkit-for-aws`. The toolkit is large. It holds 23 core skills under `skills/core-skills/`, one per service area, from IAM to Bedrock. Specialised skills sit under `skills/specialized-skills/`, grouped by category, often one per service.

The catalogue skills above are useful everywhere, so their symlinks are committed. The AWS skills are different. Each project needs a few of them, and no project needs the full set. So this repo commits no symlinks for them. You create your own, in your clone, for the skills that your current work needs:

```bash
ln -s .external/aws-agent-toolkit-for-aws/skills/core-skills/aws-iam aws-iam
ln -s .external/aws-agent-toolkit-for-aws/skills/core-skills/aws-serverless aws-serverless
```

Git ignores these symlinks, because `.gitignore` holds the pattern `aws*` and almost every toolkit skill name starts with `aws`. Your selection stays local to each clone. `git status` stays clean, and an accidental `git add -A` cannot commit your links.

The rule matches the pattern, not the toolkit. Some toolkit skills have names that do not start with `aws`, for example `amazon-bedrock` and `signing-in-to-aws`. A symlink to one of those shows as untracked. If you want a clean `git status`, add that name to `.gitignore`, under the `aws*` line.

The pattern also sets a naming rule for this repo: a tracked skill must not have a directory name that matches `aws*`. When a directory name matches an ignore pattern, git hides new files inside that directory. This rule is why the Step Functions skill is [`step-functions-jsonata`](#step-functions-jsonata) and not `aws-step-functions-jsonata`, and why the AWS triage skill lives in [`cloud-aws-failure-triage`](#cloud-aws-failure-triage). The `name:` field in the frontmatter is unaffected — both skills keep their `aws-` names there.

The [`skills` CLI](#installing) cannot install the toolkit skills, because it only sees the committed top level of this repo. Use the [clone method](#clone-into-your-skills-directory), then make the links you need.

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

If the external skills are broken symlinks, git did not check out the submodules. Run the `--init` command above.

### Adding another one

```bash
git submodule add git@github.com:<owner>/<repo>.git .external/<owner>-<repo>
ln -s .external/<owner>-<repo>/skills/<skill-name> <skill-name>
git add .gitmodules .external/<owner>-<repo> <skill-name>
```

Read the upstream licence before you add the submodule. Then add a row to the catalogue above, and a credited description under [What's in the box](#whats-in-the-box). The symlink name must match the `name:` field of the skill, because Claude Code matches on the directory name.

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

> The external skills in the [catalogue](#catalogue) are symlinks into submodules, not real directories. The CLI can fail to resolve them. If the CLI does not install them, install them from their upstream repositories, or use the clone method below.

### Clone into your skills directory

```bash
git clone --recurse-submodules git@github.com:skwashd/skills.git ~/.claude/skills
```

The repository becomes your personal skills directory. Every top-level directory is a skill, so Claude Code finds all of them at once. `.external/` and `.private/` start with a dot, so Claude Code skips them. The external skills are symlinks into `.external/`, and they resolve as normal skill directories. To update every skill, run `git pull` in `~/.claude/skills`.

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

Most skills ship an `evals/` directory containing test cases: a realistic user prompt, any input files it needs, and expectations describing what a good response contains. They cover both positive coverage ("flags X") and false positives ("does NOT flag Y" on already-good input). The `evals.json` schema is [`skill-creator`](#skill-creator)'s own — `expectations` as plain-English strings, `files` paths relative to the skill root — so its tooling runs these cases unmodified.

```
<skill>/evals/
├── evals.json       # prompts + expectations
├── files/           # fixture files, where the eval needs them
└── README.md        # what each case tests, and how to run them
```

`ship-story`'s evals cover its tracker-detection logic and its deploy-verification planning (which platform reference gets loaded, and whether read-sounding-but-mutating commands are caught), both testable offline; the middle of the workflow — branch, CI, merge — needs a live pipeline and real credentials, so those cases still need a design. The triage skills take the same offline approach from the other direction: their fixtures are captured CI logs and small Terraform projects, so `ci-failure-triage` and `cloud-aws-failure-triage` test diagnosis quality without a live pipeline or AWS account. `jira-acli` and `linear-cli` have no evals yet — a test needs a live site. `step-functions-jsonata` uses its own validator instead, because its output is machine-checkable. The validator already enforces most of what an eval can assert. Cases for the design decisions are still useful: the choice between Standard and Express, and the shape of the error handling.

External skills bring the evals of their upstream repository. `simple-english` has benchmark results in `.external/AminBlg-SimpleEnglish/evals/`.

The [`skill-creator`](#skill-creator) skill in this repository can run these cases. It benchmarks the skill against a baseline run without it, and it tunes the trigger description. A full clone includes the skill, because it is one of the external skills above.

For an informal pass, run each prompt in a fresh session with the skill in scope and check the output against the expectations by hand.

## Contributing

New skills are welcome. Before you open a PR, read the guidance in [`skill-creator`](#skill-creator) on how to author a `SKILL.md` file. The skill ships in this repository, so Claude can also scaffold and review your skill against its rules.

If you are adding or changing a skill, please add or update its evals in the same commit where the skill is testable without live credentials.

Recommendations for skills in other repositories are also welcome. Open an issue instead of a pull request, because a new external skill needs a new submodule.

## License

[MIT](./LICENSE). External skills under `.external/` keep their own licences.
