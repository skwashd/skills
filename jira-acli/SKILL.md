---
name: jira-acli
description: Read, create and update Jira work items using the Atlassian CLI (acli). Use this skill whenever the user mentions Jira, acli, an epic, a story, a ticket, a work item, an issue key, a backlog, or acceptance criteria — including when they ask to pull a ticket in, break an epic into stories, push stories to Jira, check what a ticket says, or start work from a ticket. Use it even when they do not name Jira explicitly, if the request involves work items that live in a tracker. Do not fall back to guessing acli syntax or calling the Jira REST API directly without first following the discovery steps here.
allowed-tools: Read Write Edit Glob Grep WebFetch Bash(acli *) Bash(jq *) Bash(curl *)
license: MIT
compatibility: >
  Requires acli >= 1.3 on PATH, authenticated against a Jira Cloud site
  (`acli jira auth login --web`). Writes a schema cache to `.jira/` in the
  working directory. Custom field discovery works through acli alone; the
  richer `createmeta` route additionally needs a Jira API token.
metadata:
  author: skwashd
  version: "1.2.0"
---

# Jira via acli

`acli` is Atlassian's official CLI for Jira Cloud. This skill covers reading work
items, creating them, and — the part that reliably goes wrong — writing custom fields
such as Acceptance Criteria.

## The one thing to internalise

**Discover the schema; do not assume it.**

`acli`'s own documentation is thin on custom fields, and custom field IDs differ
between Jira sites. Any command written from memory will look plausible and fail. Every
workflow below starts by asking the live instance what it expects, and ends by reading
back what was actually written.

This costs a few extra commands and saves the far more expensive failure of creating
twenty work items with an empty Acceptance Criteria field.

## Before anything else

Confirm the tool and the session:

```bash
acli --version
acli jira auth status
```

If authentication has expired, stop and tell the user to run `acli jira auth login --web`.
Do not attempt to authenticate on their behalf and do not handle their credentials.

Since March 2026 acli requires site admins to re-authorise it per connected site, because
of new OAuth scopes. If auth fails on a setup that previously worked, this is the likely
cause — say so rather than assuming the login is simply stale.

Then confirm the command surface, because `acli` changes and flags get added:

```bash
acli jira workitem create --help
acli jira workitem edit --help
acli jira workitem view --help
```

Trust that output over anything in this document. If a flag documented here is absent,
the CLI is right and this file is stale — say so rather than working around it silently.

**If you need to look something up, the reference is
<https://developer.atlassian.com/cloud/acli/reference/commands/>.** Do not web-search for
"ACLI" — the top results are Appfire's *Atlassian Command Line Interface*, an unrelated
third-party product at version 10.x–12.x with a completely different command surface.
Commands from those docs look plausible and do not exist here.

## Step 1: Discover the project schema

Cache the result so this only happens once per project per session. Write it to
`.jira/schema-<PROJECT>.json` in the working directory and read from there on subsequent
calls. **Add `.jira/` to the repository's `.gitignore`** — the cache holds custom field IDs
for the user's Jira site and should not be committed by accident.

**`acli` cannot list fields.** The `acli jira field` group has exactly three subcommands —
`create`, `delete`, `cancel-delete` — and none of them enumerate anything. There is no
`field list`. Any plan that starts by asking acli for the field catalogue is dead on
arrival; use the routes below instead.

**a. Read a populated work item with every field returned.** This is the primary route.
It is the only method that needs nothing but acli, and it gives you the field ID *and*
the exact value shape in one call — which matters, because the shape is the harder half
of the problem (see step 2).

```bash
acli jira workitem view <PROJECT>-<N> --fields "*all" --json
```

The default field set is only `key,issuetype,summary,status,assignee,description`, so
**`--fields "*all"` is mandatory here** — without it, custom fields are simply absent and
you will wrongly conclude the field does not exist. Custom fields appear in the `fields`
object keyed by ID:

```json
{
  "key": "PROJ-42",
  "fields": {
    "summary": "Existing story",
    "customfield_10122": { "type": "doc", "version": 1, "content": [] }
  }
}
```

Ask the user for a representative key whose Acceptance Criteria is already filled in. If
they do not have one, ask them to populate one item through the Jira UI — that costs them
thirty seconds and removes all the guesswork.

Note the limits: you only see IDs for fields that are **non-null on that item**, and
`*all` returns no human-readable names. Map ID to meaning by matching against values you
can recognise. If one item does not cover everything, widen the net:

```bash
acli jira workitem search --jql "project = <PROJECT> ORDER BY created DESC" \
  --fields "*all" --limit 5 --json
```

**b. Generate the creation template — as confirmation, not discovery.**

```bash
acli jira workitem create --generate-json
```

This prints a **static example** of the JSON structure. There is no evidence it accepts
`--project` or that it reflects a specific project's custom fields — the sibling
`create-bulk` command documents the same flag as "prints an example JSON structure", and
the only person known to have run it still had to supply his `customfield_NNNNN` by hand.
Use it to confirm the top-level key names, not to discover fields.

If you do run it with `--project` and the output *is* project-specific, that is new
information — tell the user, because it would be a better discovery route than (a).

**c. Jira REST, when acli is not enough.** `GET /rest/api/3/field` returns every field
with its name and type; `GET /rest/api/3/issue/createmeta` returns what a specific project
and work item type will accept, including `allowedValues` and `schema`. This is strictly
better data than (a) — names, types and permitted values together — but it needs a Jira
API token rather than the acli session. Reach for it when (a) is ambiguous, and tell the
user why you need the token rather than silently failing.

Also record from discovery:

- The exact work item type names in this project. "Epic" and "Story" are conventional
  but not guaranteed.
- Whether the project is company-managed or team-managed, since this affects how
  children attach to a parent.
- Any other mandatory fields on the create screen. A missing mandatory field fails the
  whole create.

## Step 2: Understand how each field is written

| Field | On `create` | On `edit` |
|---|---|---|
| Summary | `--summary` | `--summary` |
| Description | `--description` / `--description-file` (plain text **or** ADF) | same |
| Work item type | `--type` | `--type` |
| Project | `--project` | — |
| Labels | `--label` (comma-separated) | **`--labels`**, plus `--remove-labels` |
| Parent | `--parent <KEY>` | — |
| Assignee | `--assignee` (email, account ID, `@me`, `default`) | same, plus `--remove-assignee` |
| Target work item | *(n/a — being created)* | **`--key`** (comma-separated), or `--jql` / `--filter` |
| **Custom fields** | **`--from-json` only** | **not possible — see below** |

**The flags differ between `create` and `edit`, and the short forms collide.** This is the
easiest way to write a command that looks right and fails:

| Short | `create` | `edit` | `view` / `search` |
|---|---|---|---|
| `-l` | `--label` | `--labels` | `--limit` (search) |
| `-f` | `--from-file` | — | `--fields` |
| `-k` | — | `--key` | *(key is positional)* |

### Custom fields go under `additionalAttributes`, at create time only

There is no flag for custom fields. They go in a `--from-json` payload, under an
`additionalAttributes` object keyed by field ID:

```json
{
  "projectKey": "PROJ",
  "type": "Story",
  "summary": "Contact form submits to Lambda and publishes to EventBridge",
  "additionalAttributes": {
    "customfield_10122": { "type": "doc", "version": 1, "content": [] }
  }
}
```

`--from-json` takes a **file path**, not an inline JSON string:

```bash
acli jira workitem create --from-json workitem.json
```

Two things to be careful about:

- **Top-level key names do not mirror the CLI flags.** Community examples use `projectKey`
  rather than `project`, and the documented `create-bulk` CSV columns are `projectKey` and
  `issueType` rather than `project` and `type`. Atlassian does not publish the JSON schema.
  **Run `--generate-json` once per project and take the key names from its output** rather
  than from this table.
- **Value shape depends on field type**, because values pass straight through to the REST
  API:

  | Field type | Shape |
  |---|---|
  | Rich text (typical Acceptance Criteria) | a full **ADF document object**, not a string |
  | Select / multi-select | an **array of objects**: `[{"value": "Common"}]` |
  | Number | a bare scalar: `1234` |
  | Short text | a plain string |

  Getting this wrong is the most common failure, and a select field given
  `{"value": "Common"}` instead of `[{"value": "Common"}]` produces an unhelpful error.
  This is why step 1a's read-back matters: it shows you the exact shape Jira uses.

**Do not trust acli's error text to localise the problem.** A malformed payload can
surface as a generic "failed to generate JSON" rather than a field-level error. If the
create is rejected and the message is vague, go back and compare your payload against a
real item's `--fields "*all"` output field by field.

### acli cannot edit custom fields

`--from-json` on **`edit`** rejects `additionalAttributes` outright:

```
json: unknown field "additionalAttributes"
```

The edit template accepts only `issues`, `summary`, `type`, `description`, `assignee`,
`labelsToAdd`, `labelsToRemove`. Wrapping the field differently does not help — top-level
`customfield_NNNNN`, a `fields` wrapper, a `customFields` wrapper and human-readable names
are all rejected the same way. Atlassian have acknowledged this as a gap in the acli
wrapper; it is tracked as **[CLOUD-12876](https://jira.atlassian.com/browse/CLOUD-12876)**,
open and unresolved as a suggestion rather than a bug.

**Consequences for how you work:**

1. **Set every custom field in the `create` payload.** There is no second chance.
2. **There is no create-then-edit fallback for custom fields.** If a create is being
   rejected, debug the payload — do not create a bare item intending to fill the field in
   afterwards, because you cannot.
3. If a custom field genuinely must change on an existing item, the routes are the Jira
   REST API (`PUT /rest/api/3/issue/{key}`) or the Jira UI. Say which you are proposing
   and why, rather than silently switching to REST.

## Step 3: Validate on one before doing many

Before creating a batch of stories, create exactly one, then immediately read it back:

```bash
acli jira workitem view <NEW-KEY> --json
```

Check specifically that:

- The Acceptance Criteria field is populated and not empty or null
- The description rendered as structured content rather than as literal JSON text or
  escaped markup
- The parent link resolved to the intended epic
- The work item type is what was asked for

Only proceed to the rest of the batch once this passes. If the read-back shows an empty
custom field, the create silently succeeded while dropping the field — this is the
common failure and it is invisible unless checked.

## Step 4: Verify the batch

After creating multiple items, confirm the whole set:

```bash
acli jira workitem search --jql "parent = <EPIC-KEY> ORDER BY created ASC" --json
```

Report back to the user as a compact list of key, summary and whether acceptance
criteria are present. Never report success on the basis of the create command exiting
zero — report it on the basis of having read the items back.

## Atlassian Document Format

Descriptions accept plain text or ADF. Use ADF when structure matters — headings, lists
and code blocks in a story description are worth the extra effort. Use plain text for
short single-paragraph fields.

Keep to this subset, which renders reliably:

```json
{
  "type": "doc",
  "version": 1,
  "content": [
    { "type": "heading", "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "Context" } ] },
    { "type": "paragraph",
      "content": [
        { "type": "text", "text": "Plain text, then " },
        { "type": "text", "text": "bold", "marks": [ { "type": "strong" } ] },
        { "type": "text", "text": " and " },
        { "type": "text", "text": "code", "marks": [ { "type": "code" } ] },
        { "type": "text", "text": "." }
      ] },
    { "type": "bulletList", "content": [
        { "type": "listItem", "content": [
            { "type": "paragraph",
              "content": [ { "type": "text", "text": "A point" } ] } ] } ] },
    { "type": "codeBlock", "attrs": { "language": "python" },
      "content": [ { "type": "text", "text": "print(\"hello\")" } ] }
  ]
}
```

Notes that save debugging time:

- `version` is `1` and belongs on the top-level `doc` node.
- Every `listItem` wraps its text in a `paragraph`. Text directly inside a `listItem`
  is invalid — the validator rejects it with `text: invalid content`.
- `marks` is an array even for a single mark.
- `heading` requires `attrs.level`, and the level must be 1–6.
- Newlines inside `codeBlock` text are literal `\n` in a single text node. A `hardBreak`
  inside a `codeBlock` is rejected. **This rule is codeBlock-only** — a `\n` inside a
  *paragraph* validates but does not render as a line break; use a `hardBreak` node there.
- Ordered lists are `orderedList` with the same `listItem` structure. It optionally takes
  `attrs.order` to set the starting number.
- Lists and list items must be non-empty. `bulletList`, `orderedList` and `listItem` all
  require at least one child.

Four traps that catch Markdown-to-ADF conversion specifically:

- **The `code` mark cannot combine with any other mark** except `link`. Converting
  `` **`foo`** `` produces `marks: [{code}, {strong}]`, which fails with
  `code: unsupported mark`. Pick one.
- **It is `em`, never `italic`.** An unknown mark name is a hard rejection, not a silent
  downgrade.
- **Text nodes must be non-empty.** `{"type": "text", "text": ""}` is invalid — omit the
  node instead of emitting an empty one.
- **An empty paragraph is fine.** Both `{"type": "paragraph", "content": []}` and a bare
  `{"type": "paragraph"}` are valid, and an empty paragraph is how a blank line is
  represented. Do not strip them.

Validate before sending, rather than discovering the problem in Jira:

- JSON schema: <http://go.atlassian.com/adf-json-schema>
- Runnable validator: `@atlaskit/adf-utils` —
  `require('@atlaskit/adf-utils/validator').validator()`. This is stricter than the
  schema and catches the mark-combination rules above.

Generate ADF into a file and pass `--description-file`, rather than inlining a large
JSON string into a shell argument. Shell quoting of nested JSON is a reliable source of
corrupted payloads.

If a description renders in Jira as visible JSON, the field was treated as plain text —
check that the file contains only the JSON document with no surrounding markdown fences.

## Creating an epic and its children

1. Discover the schema (step 1). Confirm the type names.
2. Create the epic. Capture the returned key.
3. Show the user the epic key and confirm it looks right before creating children.
4. Create the first child with `--parent <EPIC-KEY>`. Read it back. Confirm parenting
   and acceptance criteria both took.
5. Create the remainder.
6. Verify the batch with JQL (step 4).

Step 4 onwards can use `acli jira workitem create-bulk`, which takes a CSV or a JSON file
of several items. Note it does not change the discipline above: create and verify **one**
item first, then bulk-create the rest. A bulk create that silently drops a custom field
across twenty items is exactly the failure this skill exists to prevent, and `create-bulk`
makes it twenty times faster to cause.

For company-managed projects `--parent` is the correct mechanism for attaching a story
to an epic. If it is rejected, do not silently switch to creating an issue link — stop
and report, because a link is not the same relationship and will look wrong on the board.

## Reading a ticket to start work from it

```bash
acli jira workitem view <KEY> --json
```

Extract the summary, description, acceptance criteria and any parent or children.
Present it back to the user as readable prose, not raw JSON. Where the description is
ADF, render it to readable markdown rather than showing the node tree.

If acceptance criteria are absent or empty, say so plainly. Do not invent them, and do
not proceed to implement against criteria you inferred without flagging that you
inferred them.

## Commenting on a work item

```bash
acli jira workitem comment create --key <KEY> --body "Comment text"
```

`--body` takes plain text or a full ADF document — the same rule as Description (see
"Atlassian Document Format" above). For anything beyond a short plain-text note, write
the ADF to a file and pass `--body-file` instead, for the same shell-quoting reason
`--description-file` is preferred over inlining.

To confirm what a comment rendered as, or to find the most recent one before editing it:

```bash
acli jira workitem comment list --key <KEY>
```

`-e/--edit-last` on `comment create` edits the last comment from the same author instead
of posting a new one — useful for correcting a comment rather than leaving both.

## Transitioning a work item

```bash
acli jira workitem transition --key <KEY> --status "Done"
```

`--status` takes the workflow status name, not an internal transition ID — the exact
names available depend on the project's workflow, so if the given name is rejected, read
the item back (`workitem view --json`) to see its current status and infer the workflow
from there rather than guessing at names.

`transition` accepts `--key` with a comma-separated list, and `--jql`/`--filter` to
target many items at once — the same wide-blast-radius shape as `edit`. Confirm before
transitioning anything beyond the single item just being closed, and never pass `-y/--yes`
on a bulk transition the user has not explicitly approved.

**Read the status back afterwards.** A transition can be rejected by the workflow (for
example, a required field is empty, or the status doesn't exist on this item's board) and
still exit in a way that's easy to misread as success:

```bash
acli jira workitem view <KEY> --json --fields status
```

## Things to ask before doing

These change other people's view of the board and are not obviously reversible:

- Deleting or archiving any work item (`workitem delete`, `workitem archive`)
- Transitioning status (`workitem transition`), particularly in bulk or via JQL
- Bulk edits across multiple keys — note `edit` accepts `--key` with a comma-separated
  list, and `--jql`/`--filter` to target many items at once, so an ordinary-looking edit
  can have a very wide blast radius
- Assigning work to someone other than the user
- Anything driven by a JQL query the user has not seen — show the query and the count
  of matching items first

`edit` also takes `-y/--yes` to skip its own confirmation prompt. Do not pass it on a
bulk operation the user has not explicitly approved; the prompt is a safety net, not
friction to route around.

Creating work items is normal and does not need per-item confirmation once the user
has agreed to the plan. Show the planned summaries before creating a batch.

## Conventions

- Australian English in all summaries, descriptions, acceptance criteria and comments.
- Acceptance criteria are written as numbered, independently checkable statements
  describing observable outcomes. Prefer "submitting the form returns a 200 and a
  message appears in the queue" over "the form works".
- Story summaries state the outcome, not the task. "Contact form submits to Lambda and
  publishes to EventBridge", not "Implement Lambda".
- Never put credentials, tokens or customer data into a work item.

## When something fails

Report the actual command and the actual error. Do not retry the same command with
cosmetic variations hoping for a different result — go back to discovery and find out
what the instance actually wants. If discovery does not resolve it, say what was tried
and hand back to the user rather than guessing further.
