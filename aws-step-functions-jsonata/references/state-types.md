# State types in JSONata mode

Field reference for each state type, showing what is required, optional, and forbidden when `QueryLanguage: "JSONata"` is active. Unless noted otherwise, every state type may also declare `QueryLanguage: "JSONata"` locally (redundant if the state machine sets it at the top level, but sometimes useful for mixed-mode state machines — which this skill does not produce).

Common to most types: `Comment`, `Assign`, `Output`. Forbidden everywhere in JSONata mode: `InputPath`, `OutputPath`, `Parameters`, `ResultSelector`, `ResultPath`, and any field ending in `Path`.

## Task

| Field | Required | Notes |
|---|---|---|
| `Type` | ✅ | `"Task"` |
| `Resource` | ✅ | Literal ARN — no JSONata. |
| `Arguments` | — | Input to the integration. Object or JSONata string. |
| `Output` | — | State's final output. Any JSON; `{% %}` strings evaluate. |
| `Assign` | — | Variable assignments. Runs in parallel with `Output`. |
| `Next` / `End` | ✅ one of | Exactly one. |
| `Retry` | — | Array of retrier objects. See `error-handling.md`. |
| `Catch` | — | Array of catcher objects. Each `Next` must route to a distinct state. |
| `TimeoutSeconds` | — | **Always set this.** Default is 99,999,999 seconds (≈3 years). |
| `HeartbeatSeconds` | — | Only meaningful with Activities or `.waitForTaskToken`. Must be strictly less than `TimeoutSeconds`. |
| `Credentials` | — | Cross-account role assumption (`RoleArn`). |

**Scope in expressions on a Task:**
- `Arguments`: `$states.input`, `$states.context` — NOT `$states.result` or `$states.errorOutput`.
- `Output`, `Assign`: `$states.input`, `$states.result`, `$states.context`.
- `Catch[i].Output`, `Catch[i].Assign`: add `$states.errorOutput`.

## Choice

| Field | Required | Notes |
|---|---|---|
| `Type` | ✅ | `"Choice"` |
| `Choices` | ✅ | Array of Choice rules. Must have at least one. |
| `Default` | — | Strongly recommended. Without it, unmatched input raises `States.NoChoiceMatched` at runtime. |
| `Output` | — | Evaluated in the matched rule's scope. |
| `Assign` | — | Evaluated in the matched rule's scope. |

Each **Choice rule** has:

| Field | Required | Notes |
|---|---|---|
| `Condition` | ✅ | Boolean literal, or JSONata string that evaluates to a boolean. |
| `Next` | ✅ | State name. |
| `Output` | — | |
| `Assign` | — | |
| `Comment` | — | |

**Forbidden in JSONata Choice rules:** every JSONPath operator — `Variable`, `And`, `Or`, `Not`, all `*Equals`/`*LessThan`/`*GreaterThan`/`*EqualsPath` comparators, all `Is*` predicates (`IsPresent`, `IsString`, etc.), `StringMatches`. Compose with JSONata operators (`=`, `!=`, `<`, `>`, `and`, `or`, `not()`, `in`) and functions (`$exists`, `$type`, `$contains`).

## Parallel

| Field | Required | Notes |
|---|---|---|
| `Type` | ✅ | `"Parallel"` |
| `Branches` | ✅ | Array of state-machine sub-objects. Each is a full `{ StartAt, States, QueryLanguage }`. |
| `Arguments` | — | Input to each branch. If omitted, each branch receives the full state input. |
| `Output` | — | `$states.result` is an array aligned to `Branches`. |
| `Assign` | — | |
| `Next` / `End` | ✅ one of | |
| `Retry` | — | Applies to the Parallel state as a whole. `States.BranchFailed` bubbles up when any branch fails. |
| `Catch` | — | |
| `TimeoutSeconds` | — | Applies to the Parallel as a whole. |

**Variable scoping across branches:** each branch has its own scope. Branches can read outer variables but cannot write to them, and cannot see each other's `Assign`s. To combine branch results, use the aggregated `$states.result` in the Parallel's `Output`.

## Map

| Field | Required | Notes |
|---|---|---|
| `Type` | ✅ | `"Map"` |
| `ItemProcessor` | ✅ | Sub-state-machine run per iteration. Has its own `StartAt`, `States`, and `ProcessorConfig`. |
| `Items` | — | Array input, or JSONata expression evaluating to an array. Required for Inline; alternative to `ItemReader` for Distributed. |
| `ItemSelector` | — | Projects each raw item before it enters `ItemProcessor`. Replaces the deprecated `Parameters`. |
| `ItemReader` | — | **Distributed only.** Reads items from S3 / a data source. |
| `ItemBatcher` | — | **Distributed only.** Groups items into batches. |
| `ResultWriter` | — | **Distributed only.** Writes output to S3. |
| `MaxConcurrency` | — | Inline: max 40. Distributed: defaults to 10,000 — **set this explicitly**. |
| `ToleratedFailureCount` / `ToleratedFailurePercentage` | — | **Distributed only.** Failure tolerance. |
| `Label` | — | Distributed child execution name prefix, ≤40 ASCII chars. |
| `Output` | — | `$states.result` is an array of iteration outputs (Inline) or an aggregate (Distributed with ResultWriter). |
| `Assign` / `Next` / `End` / `Retry` / `Catch` / `TimeoutSeconds` | — | Apply to the Map as a whole. |

**`ItemProcessor.ProcessorConfig`:**
- `Mode`: `"INLINE"` (default) or `"DISTRIBUTED"`.
- `ExecutionType`: `"STANDARD"` or `"EXPRESS"`. Required for Distributed.

**Forbidden (legacy):** `Iterator`, `ItemsPath`, `MaxConcurrencyPath`, `MaxItemsPath`, `MaxItemsPerBatchPath`, `MaxInputBytesPerBatchPath`, `ToleratedFailureCountPath`, `ToleratedFailurePercentagePath`.

**Inline vs Distributed:**

| | Inline | Distributed |
|---|---|---|
| Max concurrency | 40 | 10,000 |
| Dataset location | in-memory (≤256 KiB) | S3 / input array |
| Each iteration is… | part of parent execution | a child execution |
| History visibility | parent history | child history (truncated in parent) |
| Works in Express parent | yes | **no** |
| `ItemReader`/`ItemBatcher`/`ResultWriter` | forbidden | allowed |

**Scope inside `ItemSelector`:** in addition to `$states.input` and `$states.context`, you get `$states.context.Map.Item.Index`, `.Value`, and (inside a branched child) `.BatchInput`.

## Pass

| Field | Required | Notes |
|---|---|---|
| `Type` | ✅ | `"Pass"` |
| `Output` | — | Any JSON; evaluated from `$states.input`. |
| `Assign` | — | |
| `Next` / `End` | ✅ one of | |

**Forbidden:** `Result` (use `Output` with a literal JSON value), `ResultPath`, `InputPath`, `OutputPath`, `Parameters`.

## Wait

| Field | Required | Notes |
|---|---|---|
| `Type` | ✅ | `"Wait"` |
| `Seconds` | ✅ one of | Integer or JSONata expression evaluating to an integer. |
| `Timestamp` | ✅ one of | ISO 8601 timestamp, or JSONata expression evaluating to one. |
| `Output` | — | |
| `Assign` | — | |
| `Next` / `End` | ✅ one of | |

**Forbidden (legacy):** `SecondsPath`, `TimestampPath`.

Exactly one of `Seconds` or `Timestamp` must be present.

## Succeed

| Field | Required | Notes |
|---|---|---|
| `Type` | ✅ | `"Succeed"` |
| `Output` | — | Any JSON. |

Terminal. Does not accept `Assign` or transition fields.

## Fail

| Field | Required | Notes |
|---|---|---|
| `Type` | ✅ | `"Fail"` |
| `Error` | — | Literal string or JSONata expression. Used as the error name in execution history and EventBridge events. |
| `Cause` | — | Literal string or JSONata expression. Human-readable description. |

**Forbidden (legacy):** `ErrorPath`, `CausePath`.

Terminal. Does not accept `Output`, `Assign`, or transition fields.

**Use identifiable `Error` names** (e.g. `"ValidationRejected"`, `"PaymentFailed"`) rather than generic ones — EventBridge consumers route by this name.

## Top-level state machine fields

| Field | Required | Notes |
|---|---|---|
| `QueryLanguage` | ✅ | **Must be `"JSONata"`** for this skill. |
| `StartAt` | ✅ | Name of the first state. |
| `States` | ✅ | Object map of state name → state body. |
| `Comment` | — | |
| `Version` | — | ASL version string. |
| `TimeoutSeconds` | — | Execution-level timeout. |
