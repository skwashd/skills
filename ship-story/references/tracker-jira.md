# Adapter: Jira

Conventions only. Every command that touches Jira goes through the `jira-acli` skill —
call the Skill tool with `jira-acli` rather than improvising `acli` syntax here. Its
premise is that `acli`'s custom-field handling is site-specific and undocumented; a
command written from memory looks plausible and fails.

## Resolve the key

The work item key is exactly as Jira gives it — `PROJ-123`. Uppercase project prefix,
hyphen, number. No other form is valid.

## Read the work item

Call the Skill tool with `jira-acli` to read the ticket. Acceptance criteria typically
live in a **custom field**, not the description — `jira-acli`'s discovery procedure
finds the field ID for this site. If acceptance criteria come back empty, that skill's
own rule applies: say so plainly, do not invent them.

## Branch

The bare key, exactly as Jira gives it — no case change, no slug, nothing appended:

```
PROJ-123
```

## Commit

First line is `[<KEY>] <summary>`, key in square brackets at the start:

```
[PROJ-123] Add server-side validation to the contact form
```

## Pull request

Title: `[<KEY>] <summary>`. Body references the key and, per `ship-story` step 5, lists
what will be verified after deployment.

## Comment

Call the Skill tool with `jira-acli` to post the verification summary as a comment on
the item.

## Close

**Jira does not transition a work item on merge.** Unlike Linear and GitHub Issues,
there is no default integration that does this for you — the transition is a deliberate
step, and it needs confirmation first (`ship-story`'s "Confirm before" list covers this).
Call the Skill tool with `jira-acli` to transition the item once the user has confirmed,
then read it back to confirm the transition actually took — a rejected transition (a
required field empty, a status name that doesn't exist on this board) doesn't always
fail loudly.

## Anything deeper

Creating the story in the first place, breaking an epic into stories, bulk operations,
custom-field discovery, ADF formatting — all of that is `jira-acli`'s territory, not
this adapter's. Call the Skill tool with `jira-acli`.
