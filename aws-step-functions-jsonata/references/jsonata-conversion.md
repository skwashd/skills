# JSONPath → JSONata conversion cheat sheet

Use this when porting a legacy JSONPath state machine or when converting an AWS example from the docs to JSONata mode. Every row goes one way only: **JSONPath (old) → JSONata (new).** If the JSONPath side of a row still appears in a state machine you're editing, it must be removed.

## Expression wrapping

JSONPath strings are implicit and unwrapped. JSONata strings are wrapped in `{% … %}` **exactly** — no whitespace between the braces and the delimiter.

```
"id.$": "$.orderId"                  →  "id": "{% $states.input.orderId %}"
```

Field names with `.$` suffix are forbidden; replace the suffix convention with ordinary field names plus wrapped expressions.

## Context objects

| JSONPath | JSONata |
|---|---|
| `$` (task input) | `$states.input` |
| `$$` (execution context) | `$states.context` |
| `$$.Execution.Name` | `$states.context.Execution.Name` |
| `$$.Task.Token` | `$states.context.Task.Token` |
| `$$.Map.Item.Value` | `$states.context.Map.Item.Value` |
| (no equivalent — `ResultPath`-based) | `$states.result` (only in Task/Map/Parallel `Output` / `Assign`) |
| (no equivalent — error output via `Catch.ResultPath`) | `$states.errorOutput` (only in `Catch[]` scope) |

**Critical rule:** inside a `{% %}` expression, bare `$` and `$$` alone are forbidden. You MUST qualify with `$states.input` / `$states.context` / etc.

## State-level I/O fields

| JSONPath | JSONata equivalent |
|---|---|
| `InputPath` | (nothing — use `$states.input.*` directly inside `Arguments` / `Output`) |
| `Parameters` | `Arguments` (on Task, Parallel, Map `ItemReader`/`ResultWriter`) |
| `ItemsPath` (Map) | `Items` |
| `Parameters` → child (Map) | `ItemSelector` |
| `ResultSelector` | (subsumed — transform inside `Output`) |
| `ResultPath: "$.sum"` | `"Output": "{% $merge([$states.input, { 'sum': $states.result }]) %}"` |
| `OutputPath` | (nothing — `Output` already sets the state's final output) |
| `Result` (Pass state) | `Output` (constant value — can still be a plain JSON literal) |

## Choice state

| JSONPath | JSONata |
|---|---|
| `"Variable": "$.x", "StringEquals": "foo"` | `"Condition": "{% $states.input.x = 'foo' %}"` |
| `"Variable": "$.n", "NumericGreaterThan": 10` | `"Condition": "{% $states.input.n > 10 %}"` |
| `"Variable": "$.list", "IsPresent": true` | `"Condition": "{% $exists($states.input.list) %}"` |
| `"Variable": "$.x", "StringMatches": "a*"` | `"Condition": "{% $contains($states.input.x, /a.*/) %}"` or `$match` |
| `"And": [rule1, rule2]` | `"Condition": "{% (cond1) and (cond2) %}"` |
| `"Or": [rule1, rule2]` | `"Condition": "{% (cond1) or (cond2) %}"` |
| `"Not": rule` | `"Condition": "{% not(cond) %}"` |
| `"Variable": "$.x", "IsNull": true` | `"Condition": "{% $states.input.x = null %}"` |
| `"Variable": "$.x", "IsString": true` | `"Condition": "{% $type($states.input.x) = 'string' %}"` |
| `"Variable": "$.x", "IsNumeric": true` | `"Condition": "{% $type($states.input.x) = 'number' %}"` |

The entire JSONPath Choice rule schema (`Variable`, `And`, `Or`, `Not`, every comparator, every `Is*` predicate) is gone — JSONata Choice rules have only `Condition`, `Next`, and optional `Output` / `Assign` / `Comment`.

## Intrinsic functions → JSONata

All the `States.*` intrinsic functions go away in JSONata mode; use JSONata operators and functions.

| Intrinsic | JSONata |
|---|---|
| `States.Format('hello {}', $.name)` | `'hello ' & $states.input.name` |
| `States.Array(a, b, c)` | `[a, b, c]` |
| `States.ArrayContains($.list, $.v)` | `$states.input.v in $states.input.list` |
| `States.ArrayLength($.list)` | `$count($states.input.list)` |
| `States.ArrayGetItem($.list, 2)` | `$states.input.list[2]` |
| `States.ArrayPartition($.list, 10)` | `$partition($states.input.list, 10)` |
| `States.ArrayRange(1, 10, 2)` | `$range(1, 10, 2)` |
| `States.ArrayUnique($.list)` | `$distinct($states.input.list)` |
| `States.JsonToString($.obj)` | `$string($states.input.obj)` |
| `States.StringToJson($.text)` | `$parse($states.input.text)` (⚠ not `$eval` — blocked) |
| `States.JsonMerge(a, b, false)` | `$merge([a, b])` |
| `States.UUID()` | `$uuid()` |
| `States.Hash(src, 'SHA-256')` | `$hash(src, 'SHA-256')` |
| `States.Base64Encode(x)` | `$base64encode(x)` |
| `States.Base64Decode(x)` | `$base64decode(x)` |
| `States.StringSplit($.s, ',')` | `$split($states.input.s, ',')` |
| `States.MathAdd(a, b)` | `a + b` |
| `States.MathRandom(0, 10)` | `$random() * 10 | $floor` (careful — `$random` is 0–1) |

## AWS-added JSONata extensions

Step Functions adds these to the standard JSONata surface:

| Function | What it does |
|---|---|
| `$partition(array, size)` | Split an array into fixed-size chunks |
| `$range(start, end, step)` | Integer range (step optional, default 1) |
| `$hash(source, algorithm)` | Algorithms: `MD5`, `SHA-1`, `SHA-256`, `SHA-384`, `SHA-512` |
| `$random([seed])` | Pseudo-random; optional seed for determinism |
| `$uuid()` | Random UUID v4 |
| `$parse(jsonString)` | Parse JSON (replaces blocked `$eval`) |

## Common idioms

**Merge result into input (old `ResultPath` equivalent):**
```json
"Output": "{% $merge([$states.input, { 'summary': $states.result }]) %}"
```

**Preserve input and stash error in a Catch:**
```json
"Catch": [
  { "ErrorEquals": ["SomeError"], "Next": "Handle",
    "Output": "{% $merge([$states.input, { 'error': $states.errorOutput }]) %}" }
]
```

**Pull Lambda Invoke Payload out while keeping input:**
```json
"Output": "{% $merge([$states.input, $states.result.Payload]) %}"
```

**Check membership:**
```json
"Condition": "{% $states.input.type in ['order', 'refund', 'chargeback'] %}"
```

**Build a derived identifier:**
```json
"Assign": {
  "correlationId": "{% $states.context.Execution.Name & '-' & $states.input.requestId %}"
}
```

**Iterate over a filtered list (Map.Items):**
```json
"Items": "{% $states.input.records[status = 'pending'] %}"
```

## Things that look JSONata but aren't allowed

- `$eval("1+1")` — blocked by Step Functions. Use `$parse` for JSON parsing or precompute.
- Elvis `?:` and null-coalesce `??` (JSONata 2.1 syntax) — Step Functions runs JSONata 2.0.6 and rejects these. Local parsers (including `jsonata-python`) will accept them; AWS validation will not. Use ternary `cond ? a : b` and explicit null checks.
- Bare `$`, `$$`, or unqualified field names at the top of an expression — forbidden. Reach through `$states.*` or named variables (`$myVar`).
