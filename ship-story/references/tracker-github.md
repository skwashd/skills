# Adapter: GitHub Issues

No standalone skill for this tracker — `gh issue` covers the whole path, and it's
already a dependency of `ship-story` for PRs and CI. For anything unusual, `gh issue
--help` and `gh api` are the escape hatches.

## Resolve the key

The issue number, e.g. `123`, or a bare `#123` in conversation. A full
`github.com/<owner>/<repo>/issues/123` URL resolves the same issue in a different repo
than the one checked out — confirm you're in the right repo before acting on it.

## Read the work item

```bash
gh issue view 123 --json title,body,state,labels,assignees,parent,subIssues
```

**Acceptance criteria live in the body, often as a markdown task list, with no dedicated
field to fall back on.** If the body doesn't state them, or the task list is empty or
vague, stop and ask — there's nowhere else to look.

## Branch

```bash
gh issue develop 123 --checkout
```

Creates a branch linked to the issue and checks it out. `gh` names it from the issue
unless you pass `--name` — leave it to `gh` rather than overriding it, so the branch
stays linked in GitHub's UI.

## Commit

Reference the issue number in the first line:

```
#123 Add server-side validation to the contact form
```

## Pull request

```bash
gh pr create --title "#123 <summary>" --body-file pr-body.md
```

Per `ship-story` step 5, `pr-body.md` needs the reference, the change description and
the verification checklist. Include a `Closes #123` line — this is what makes GitHub
auto-close the issue on merge, and it only fires **when the PR merges into the
repository's default branch**. A PR merged into any other branch will not close it.

## Comment

```bash
gh issue comment 123 --body "…"
```

## Close

Check whether `Closes #123` already closed it before closing again:

```bash
gh issue view 123 --json state,stateReason
```

If it's still open — the PR merged into a non-default branch, or the closing keyword
was missed — close it explicitly:

```bash
gh issue close 123 --comment "…" --reason completed
```

## Anything deeper

There's no adapter beyond this. `gh issue create`, `gh issue edit`, and `gh issue
develop --list` cover creating and managing issues directly; `gh api` covers anything
`gh issue` doesn't expose a flag for.
