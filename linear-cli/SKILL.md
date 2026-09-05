---
name: linear-cli
description: Read, create and update Linear issues using the Linear CLI (`linear`, schpet/linear-cli). Use this skill whenever the user mentions Linear, an issue, a project, a milestone, a cycle, a backlog, or acceptance criteria in a Linear context — including when they ask to pull an issue in, break a project into issues, push issues to Linear, check what an issue says, or start work from one. Use it even when they do not name Linear explicitly, if the request involves work items that live in a tracker and the project is configured for Linear. In chat or Cowork surfaces without a local CLI, the equivalent is the Linear MCP server rather than this skill.
allowed-tools: Read Write Edit Glob Grep Bash(linear *)
license: MIT
compatibility: >
  Requires the `linear` CLI (schpet/linear-cli) on PATH, authenticated
  (`linear auth login`). Reads and writes `.linear.toml` in the working directory via
  `linear config`, which records the default workspace and team so most commands need
  no `--workspace`/`--team` flags. This skill is the CLI path; the Linear MCP server is
  the equivalent for chat and Cowork sessions where a local CLI isn't available.
metadata:
  author: skwashd
  version: "1.0.0"
---

# Linear via the CLI

`linear` (schpet/linear-cli) is a third-party but actively maintained CLI for Linear.
Unlike Jira, there is no custom-field discovery problem here: descriptions are plain
markdown, and acceptance criteria live in the description itself rather than a
dedicated field. What still needs care is that **labels, projects, milestones, cycles
and workflow states are all workspace- or team-specific** — don't assume a name exists
before you've listed it.

## Before anything else

Confirm the tool and the session:

```bash
linear --version
linear auth whoami
```

If authentication has expired or `whoami` fails, stop and tell the user to run `linear
auth login`. Do not attempt to authenticate on their behalf.

`linear auth list` shows every configured workspace; `--workspace <slug>` on any command
targets one explicitly when more than one is configured. Most repositories only need
one, set up once via:

```bash
linear config
```

This writes `.linear.toml` in the working directory, recording the default workspace and
team. **Add `.linear.toml` to the repository's `.gitignore`** if it hasn't been already
— treat it the same as any other local credential-adjacent config. Its presence is also
what `ship-story` uses to detect that a project uses Linear, so don't remove it once a
project is working.

Then confirm the command surface, because the CLI evolves:

```bash
linear issue create --help
linear issue update --help
linear issue view --help
```

Trust that output over anything in this document.

## Reading an issue

```bash
linear issue view <issueId> --json
```

Or, from a checkout already on the issue's branch:

```bash
linear issue id
```

**Acceptance criteria live in the markdown description.** There is no separate field —
if you're used to Jira's custom field, that's the one habit to unlearn. If the
description doesn't state them, or states them vaguely, say so plainly. Do not invent
them and do not proceed to implement against criteria you inferred without flagging that
you inferred them.

## Creating an issue

```bash
linear issue create --title "…" --description-file body.md --team <TEAM>
```

`--description-file` is preferred over `--description` for anything beyond a short
single-line body, for the same shell-quoting reason it matters in any CLI — a large
inline string is a reliable source of corrupted content.

Useful flags, all workspace/team-specific so confirm names first if unsure:

| Flag | For |
|---|---|
| `--parent <team_number>` | attach as a child of an existing issue |
| `--project <uuid\|slug\|name>` | attach to a project |
| `--milestone <name>` | attach to a project milestone (needs `--project`, or the issue already having one) |
| `--cycle <name\|now\|next\|+1>` | attach to a cycle |
| `--label <name>` | apply a label; repeat for multiple |
| `--assignee <self\|name>` | assign |
| `--estimate <points>` | points estimate |
| `-s/--state <name>` | initial workflow state |
| `--start` | start the issue immediately after creating it |

## Breaking a project down

1. Confirm the team and project first — `linear team list`, `linear project list`. Don't
   guess a team key or project name; both are workspace-specific.
2. Create the parent (a project, or a parent issue via `--parent`).
3. Create the first child. Read it back (`linear issue view <id> --json`) and confirm
   the parent link, description and any labels took.
4. Create the remainder once the first one is right.
5. Verify the batch:

```bash
linear issue query --project <project> --json
```

Report back to the user as a compact list of identifier, title, and whether the
description states acceptance criteria. Report success on the basis of the read-back,
not on the create command exiting zero.

## Updating an issue

```bash
linear issue update <issueId> --state "<name>" --add-label "<name>"
```

`update` mirrors `create`'s attachment flags (`--parent`, `--project`, `--milestone`,
`--cycle`, `--assignee`), plus `--add-label`/`--remove-label` for incremental label
changes without replacing the whole set (`--label` on its own **replaces** it).

**Workflow state names are team-specific.** `issue query`'s `--state` filter accepts the
canonical *type* (`triage`, `backlog`, `unstarted`, `started`, `completed`, `canceled`),
but `issue update --state` takes the team's own *name* for a state (e.g. `"In Review"`,
which might not exist on a different team). If a state name is rejected, read the issue
back to see what's actually on its board rather than guessing a second name.

## Commenting

```bash
linear issue comment add <issueId> --body "…"
```

Supports replying to a thread and `--attach` for inline images. `linear issue comment
list <issueId>` reads existing comments back.

## Labels, teams, projects — discover before you use a name

None of these are enumerable from memory reliably:

```bash
linear label list --all
linear team list
linear project list
```

A label, team key or project name that doesn't exist fails the create or update outright
— check first rather than retrying variations.

## Things to ask before doing

- Deleting an issue (`issue delete`), especially `--bulk`/`--bulk-file`/`--bulk-stdin`,
  which can remove many issues from one command
- Deleting a team or a project
- Transitioning many issues at once via a query rather than a single `--issueId`
- Assigning work to someone other than the user

`issue delete` takes `-y/--confirm` to skip its own prompt. Don't pass it on anything
the user hasn't explicitly approved.

Creating issues is normal and does not need per-item confirmation once the user has
agreed to the plan. Show the planned titles before creating a batch.

## Conventions

- Australian English in all titles, descriptions and comments.
- Acceptance criteria are numbered, independently checkable statements describing
  observable outcomes — "submitting the form returns a 200 and a message appears in the
  queue", not "the form works".
- Issue titles state the outcome, not the task.
- Never put credentials, tokens or customer data into an issue.

## Shipping a Linear issue

For the branch, commit, PR and close conventions used once work on an issue starts, see
`ship-story`'s Linear adapter (`references/tracker-linear.md`) rather than duplicating
that sequence here — this skill covers reading, creating and maintaining issues, not the
git/PR mechanics.

## When something fails

Report the actual command and the actual error. Do not retry the same command with
cosmetic variations hoping for a different result — list the actual labels, teams or
projects and find out what the workspace actually has. If that doesn't resolve it, say
what was tried and hand back to the user rather than guessing further.
