# Adapter: Linear

Ship-time commands live here, since the `linear` CLI is small enough not to need a
separate skill for this path. Call the Skill tool with `linear-cli` for anything beyond
it — creating issues, breaking work down, bulk changes.

## Resolve the key

```bash
linear issue id
```

Prints the issue for the current git branch — use this rather than asking the user to
repeat a key you can read from the checkout.

## Read the work item

```bash
linear issue view <issueId>
```

**Acceptance criteria live in the markdown description — there is no dedicated field**
the way Jira has one. If the description doesn't state them, or states them vaguely,
stop and ask rather than inferring them from the title.

## Branch

```bash
linear issue start <issueId>
```

This creates and checks out the branch. Left alone, it names the branch after the issue
identifier — the CLI's own `--branch` flag is documented as "a custom name to use
**instead of** the issue identifier," which is the default. Use the default rather than
overriding it with `-b`; downstream Linear automation is set up to recognise it.

## Commit

```bash
linear issue describe <issueId>
```

Prints the issue title and a **Linear-issue trailer** (a magic-word line such as `Fixes
ENG-45`) formatted for direct use as commit content. Use the title as your first line,
or your own summary if it needs more precision, and carry the trailer into the commit
body — that trailer is part of what lets Linear's GitHub integration link the commit to
the issue. `-r/--references` swaps `Fixes` for `References`, if closing on merge isn't
intended.

## Pull request

```bash
gh pr create --title "<summary>" --body-file pr-body.md
```

Per `ship-story` step 5, `pr-body.md` needs the reference, the change description and
the verification checklist — include the same `Fixes <issueId>` trailer from `linear
issue describe` near the top, so the PR itself carries the link. (`linear issue
pull-request` also exists and prefixes the issue ID onto the title automatically, but it
doesn't produce the verification checklist step 5 requires, so `gh pr create` with an
explicit body stays the more complete route.)

## Comment

```bash
linear issue comment add <issueId>
```

## Close

Linear's GitHub integration can auto-transition the issue on merge — via the linked
branch from `issue start`, or via the magic-word trailer in the PR body. **Don't assume
which one fired; check.**

```bash
linear issue view <issueId>
```

If it's still open, transition it explicitly:

```bash
linear issue update <issueId> --state "<state name>"
```

`--state` takes the workflow state's name — this is team-specific, so if a guessed name
(`"Done"`) is rejected, read the issue back first to see what states are actually on its
board.

## Anything deeper

Creating issues, breaking work down (`--parent`, `--project`, `--milestone`), labels,
cycles, bulk changes — call the Skill tool with `linear-cli`.
