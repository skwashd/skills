# Express vs Standard

Pick Standard by default. Use Express only when the profile below fits *all* your requirements, because Express asks you to design more carefully in exchange for price and throughput.

## The decision matrix

|  | Standard | Express |
|---|---|---|
| Max duration | 1 year | **5 minutes** |
| Delivery | exactly-once | **at-least-once** |
| Pricing | $0.000025 per state transition | $1.00 per million executions + $0.00001667 per GB-second |
| Start throughput | 2,000 executions/sec | **100,000 executions/sec** |
| State transition throughput | service-limited | unlimited |
| Integration patterns | Request/Response, `.sync`, `.waitForTaskToken` | **Request/Response only** |
| Activities | supported | **not supported** |
| Distributed Map parent | supported | **not supported** |
| Execution history API | 90 days, queryable | none — CloudWatch Logs only |
| Redrive-from-failed-state | supported | not supported |
| EventBridge execution events | `Step Functions Execution Status Change` | only if logs → EventBridge is configured |

## Decision rubric

Use **Express** only if all of these hold:

1. Expected max duration ≤ 5 minutes (with room to spare).
2. Every Task is **idempotent** (at-least-once delivery makes duplicates possible).
3. You don't need `.sync`, `.waitForTaskToken`, or Activities.
4. You don't need a Distributed Map in this workflow.
5. You're either high-volume (>10 executions/sec sustained) or cost-sensitive *and* you accept that debugging requires CloudWatch Logs rather than execution history.

Use **Standard** in every other case. It is the sensible default for:
- Any workflow that could take more than a few minutes
- Sagas and compensating transactions
- Human-in-the-loop approvals
- Batch processing with Distributed Map
- Anything that calls `.sync` integrations (ECS, Batch, Glue, SageMaker, nested SM)
- Workflows where redrive-from-failed-state matters operationally

## Error-handling implications

The two types ask for different error-handling postures:

**Standard: fail loud on unknown errors.**
- Execution history is preserved for 90 days via the API.
- EventBridge emits `Step Functions Execution Status Change` events; route `status: FAILED` to pager/SNS/lambda.
- Operators inspect history, fix the bug, and `RedriveExecution` from the failed state with the original input.
- Therefore: do not catch `States.ALL`. Catch only named, recoverable business outcomes. Unknown errors should propagate.

**Express: small and defensive; catch everything.**
- There is no execution history. CloudWatch Logs is the only record, and only if logging is enabled.
- Operators can't redrive. If the execution fails, diagnosis depends on log output — so the workflow must emit structured output on failure paths.
- Therefore: every Task has a `States.ALL` catcher that routes to a distinct handler per Task. Handlers emit structured JSON to SNS, EventBridge, or CloudWatch Logs.
- Keep the workflow short (≤10 states). If it grows past that, split it: Standard parent invokes Express children via `arn:aws:states:::states:startExecution.sync:2`.

## Nesting pattern: Standard parent, Express children

When you have a high-throughput idempotent inner sequence (e.g. transforming a stream of events) that fits under 5 minutes, but the overall orchestration needs exactly-once semantics or `.sync` integrations, nest an Express state machine inside a Standard parent:

```
Standard parent:
  FetchWork → StartExpressChildren (Map, DISTRIBUTED + EXPRESS) → AggregateResults → Decide
```

The Standard parent gives you redrive, the Distributed Map gives you fan-out to 10,000 concurrent children, and each Express child is small and defensive. This is the go-to pattern for event-processing pipelines.

## Cost quick-calc

Example: 1 million executions per day, each making 10 state transitions.

- **Standard:** 1M × 10 × $0.000025 = $250/day ≈ $7,500/month.
- **Express:** 1M × $1.00/M + GB-second charges ≈ $1 + (1M × memory × duration × $0.00001667). Even at 256 MB for 1 second each, that's 1M × 0.25 × 1 × $0.00001667 ≈ $4/day for duration, so ~$5/day ≈ $150/month.

That's a 50× cost reduction for this workload, which is why Express is compelling for high-volume event processing — but only when the workload fits the constraints.

## What you give up with Express

- Execution history (none beyond what you explicitly log).
- Redrive-from-failed-state.
- Wait states > 5 minutes (the whole execution has a 5-minute cap).
- Task tokens and callbacks.
- `.sync` patterns.
- Activities.
- Distributed Map as the parent (you can still have an Express workflow run as a Distributed Map *child*).
- The emotional comfort of knowing an operator can inspect exactly what happened three weeks ago.
