# Error handling in JSONata-mode Step Functions

This is the most opinionated document in the skill. Read it before writing any `Retry` or `Catch` block.

## Core principle: never build a common error handler

Most tutorials (and the default AWS Workflow Studio patterns) route every `Catch` block to a single `HandleError` state. **Don't do this.** The common-error-handler pattern creates three specific problems:

1. **It breaks redrive-from-failed-state.** When an error routes to a common handler, the execution *transitions past* the state that actually failed. After a fix is deployed, the operator cannot redrive from that state — they must re-run the whole workflow from `StartAt`, which may re-trigger side effects (re-charge cards, re-send emails, re-publish events) that the workflow already performed.
2. **It turns failures into successes.** If the handler finishes without raising, the execution reports `Succeeded`, not `Failed`. EventBridge does not emit a `Step Functions Execution Status Change` event with `status: FAILED`. Paging rules never fire. Failure metrics look clean.
3. **It hides the failure location.** Which Task actually failed is now buried in the handler state's input rather than shown at the top of execution history.

The alternative is plain but effective:

- **Retry on the state** for transient, idempotent failures (throttling, 5xx, network blips).
- **Catch on the state** only for *known, named, recoverable business outcomes* — and route each one to a *distinct* handler state, not a shared one.
- **Don't catch unknown errors.** Let the execution fail where the error happened. Configure EventBridge to alert on failures. Operators inspect history, fix, and redrive.

## Retry hygiene

Retry is the right tool when the same operation might succeed if we just try again with no other change. That means transient errors only.

```json
"Retry": [
  {
    "ErrorEquals": [
      "Lambda.TooManyRequestsException",
      "Lambda.ServiceException",
      "Lambda.AWSLambdaException",
      "Lambda.SdkClientException"
    ],
    "IntervalSeconds": 2,
    "MaxAttempts": 6,
    "BackoffRate": 2.0,
    "MaxDelaySeconds": 60,
    "JitterStrategy": "FULL"
  },
  {
    "ErrorEquals": ["States.QueryEvaluationError"],
    "MaxAttempts": 0
  }
]
```

Key rules:

- **Never retry `States.QueryEvaluationError`.** It means a JSONata expression failed to evaluate — deterministic, always fails the same way. Include a `MaxAttempts: 0` retrier for it on JSONata-heavy Tasks so the execution fails fast instead of waiting through the default exponential backoff.
- **`BackoffRate` must be ≥ 1.0.** A value of 1.0 means constant interval; higher means exponential.
- **`MaxDelaySeconds`** caps exponential growth so you don't end up with 8-minute waits.
- **`JitterStrategy: "FULL"`** adds uniform-random delay jitter; always use it to prevent thundering herds.
- **`States.ALL` must be the only entry in its `ErrorEquals`** and **must be the last retrier** in the array. It shadows everything after it. In practice you almost never want `States.ALL` in a Retry block — it just masks bugs.
- Common service-specific retryable errors to consider: `DynamoDB.ThrottlingException`, `DynamoDB.ProvisionedThroughputExceededException`, `S3.SlowDown`, `EventBridge.EventBridgeException`, `SNS.SNSException`, `SQS.AWS.SimpleQueueService.NonExistentQueue` (no — that one is permanent; don't retry it).

## Catch hygiene

Catch is the right tool when a specific, named error is a *business outcome* that the workflow must respond to differently — not the same thing as a system failure.

```json
"Catch": [
  {
    "ErrorEquals": ["CardDeclined"],
    "Next": "NotifyCustomerDeclined",
    "Output": "{% { 'orderId': $states.input.orderId, 'reason': $states.errorOutput.Cause } %}"
  },
  {
    "ErrorEquals": ["InventoryUnavailable"],
    "Next": "Backorder",
    "Output": "{% $merge([$states.input, { 'error': $states.errorOutput }]) %}"
  }
]
```

Key rules:

- **Each catcher's `Next` points to a distinct, purpose-specific state.** Do not merge them into one shared handler.
- **`$states.errorOutput` is only available inside `Catch[].Output` / `Catch[].Assign`.** The validator flags this as an error if you use it elsewhere.
- **Emit preserved input plus error details** using the `$merge` pattern. This is the idiomatic JSONata replacement for the old JSONPath `ResultPath` convention.
- **Avoid `States.ALL` in a Standard workflow.** It is the common-handler pattern in disguise.

## The Output idiom: `$merge` replaces `ResultPath`

In JSONPath mode, `"ResultPath": "$.sum"` tucked the task result under the input at `$.sum`. In JSONata mode you build the merge explicitly:

```json
"Output": "{% $merge([$states.input, { 'sum': $states.result }]) %}"
```

For catchers, the equivalent "stash the error next to the input" pattern:

```json
"Output": "{% $merge([$states.input, { 'error': $states.errorOutput }]) %}"
```

## Uncatchable errors

Two errors cannot be caught at all:

- `States.DataLimitExceeded` — raised when a payload exceeds 256 KiB. Fix by reducing payload size; for Map, split into smaller batches.
- `States.Runtime` — an internal Step Functions failure that indicates a deep structural problem. Not retryable.

`States.ALL` does NOT catch either of these, and neither do any named catchers. Do not rely on Catch logic for these.

## Worked example: Standard — fail loud

```json
"ChargeCard": {
  "Type": "Task",
  "Resource": "arn:aws:states:::lambda:invoke",
  "Arguments": { "FunctionName": "${ChargeFn}", "Payload": "{% $states.input %}" },
  "Retry": [
    {
      "ErrorEquals": ["Lambda.TooManyRequestsException", "Lambda.ServiceException",
                      "Lambda.AWSLambdaException", "Lambda.SdkClientException"],
      "IntervalSeconds": 2, "MaxAttempts": 6, "BackoffRate": 2.0,
      "MaxDelaySeconds": 60, "JitterStrategy": "FULL"
    }
  ],
  "Catch": [
    {
      "ErrorEquals": ["CardDeclined", "InsufficientFunds"],
      "Next": "RefundReservation",
      "Output": "{% $merge([$states.input, { 'error': $states.errorOutput }]) %}"
    }
  ],
  "TimeoutSeconds": 30,
  "Output": "{% $merge([$states.input, $states.result.Payload]) %}",
  "Next": "FulfillOrder"
}
```

**What gets caught:** only `Lambda.*` transient throttling (retried) and two named business outcomes (caught). Everything else — `States.Timeout`, `PaymentProviderOutage`, `States.TaskFailed` with an unknown cause — propagates. The execution fails at `ChargeCard`, EventBridge fires a `FAILED` event, operators look at history, fix whatever broke, and redrive from `ChargeCard` once the fix is live.

## Worked example: Express — small and defensive

Express has no execution history. So defensive catchers are legitimate, but they must emit structured output rather than silently swallow:

```json
"TransformEvent": {
  "Type": "Task",
  "Resource": "arn:aws:states:::lambda:invoke",
  "Arguments": { "FunctionName": "${TransformFn}", "Payload": "{% $states.input %}" },
  "Retry": [
    {
      "ErrorEquals": ["Lambda.TooManyRequestsException", "Lambda.ServiceException",
                      "Lambda.AWSLambdaException", "Lambda.SdkClientException"],
      "IntervalSeconds": 1, "MaxAttempts": 5, "BackoffRate": 2.0,
      "JitterStrategy": "FULL"
    },
    {
      "ErrorEquals": ["States.QueryEvaluationError"],
      "MaxAttempts": 0
    }
  ],
  "Catch": [
    {
      "ErrorEquals": ["States.ALL"],
      "Next": "ReportTransformFailure",
      "Output": "{% { 'stage': 'TransformEvent', 'input': $states.input, 'error': $states.errorOutput } %}"
    }
  ],
  "TimeoutSeconds": 15,
  "Output": "{% $states.result.Payload %}",
  "Next": "EmitEvent"
}
```

`ReportTransformFailure` then publishes the structured output to SNS, EventBridge, or CloudWatch Logs so operators have something to read. Even under Express, catchers point to *distinct* handler states per originating Task — so you know from the handler's name which Task failed. See `templates/express-defensive.asl.json` for the full pattern.

## The predefined error names, briefly

| Name | Catchable? | Notes |
|---|---|---|
| `States.ALL` | — | Matches all catchable errors. Must be last and alone. |
| `States.DataLimitExceeded` | **no** | Payload > 256 KiB. Not even `States.ALL` catches this. |
| `States.Runtime` | **no** | Internal SFN failure. |
| `States.TaskFailed` | yes | Generic task failure; wildcard for most known Task errors (except Timeout). |
| `States.Timeout` | yes | Task didn't finish within `TimeoutSeconds` (or missed a heartbeat). |
| `States.HeartbeatTimeout` | yes | Explicit heartbeat miss — only meaningful for Activities and `.waitForTaskToken`. |
| `States.Permissions` | yes | IAM permission error. |
| `States.ExceedToleratedFailureThreshold` | yes | Distributed Map exceeded its failure tolerance. |
| `States.BranchFailed` | yes | A Parallel branch failed. |
| `States.QueryEvaluationError` | yes | **JSONata expression failed.** Never retry this — deterministic. |
| `States.ItemReaderFailed` / `ResultWriterFailed` | yes | Distributed Map I/O. |
| `Lambda.TooManyRequestsException` | yes | Throttling — always retry with backoff. |
| `Lambda.ServiceException` / `AWSLambdaException` / `SdkClientException` | yes | Transient; retry. |
| `Sandbox.Timedout` | yes | Lambda container timed out. |

## When you think you want a common handler

Common reasons people reach for a common handler, and what to do instead:

- *"I want to always send a notification on failure."* → Configure an EventBridge rule on `detail-type: "Step Functions Execution Status Change"` with `status: FAILED` and attach SNS/PagerDuty/Slack as the target. This works across every state machine in the account and doesn't pollute the ASL.
- *"I want to write a failure record to DynamoDB."* → Same EventBridge rule, target Lambda that writes the record. Gives you structured failure data with zero ASL overhead and a consistent schema across state machines.
- *"I want to compensate on any failure."* → Compensation is rarely general; it depends on what already happened. Use the Saga pattern (see `templates/standard-saga-compensation.asl.json`) where each state routes to its own compensator that undoes *its* preceding work.
- *"The workflow is Express and I need visibility."* → The Express-defensive pattern is fine, but every catcher still routes to a distinct, named handler per Task so the handler's name is the signal for where the failure occurred.
