# Verifying on AWS

Platform detail for step 8 of `ship-story`, for projects that deploy to AWS. The
generic rules — read-only first, name every write, never mutate around a permissions
boundary — are in the skill itself; this file is only the AWS commands and their traps.

## Read-only observation

These change nothing:

- **Structured logs** — `aws logs tail /aws/lambda/<fn> --since 5m --format short`
  (`--since` takes a single unit — `5m` or `1h`, not `1h30m`)
- **Queue depth** — `aws sqs get-queue-attributes --queue-url <url> --attribute-names
  ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible`
- **Stack contents** — `aws cloudformation describe-stack-resources --stack-name <name>`
  (returns the first 100 resources with no pagination; use `list-stack-resources` for
  larger stacks)

## The trap: `aws sqs receive-message` is not read-only

It makes the message invisible to genuine consumers for the visibility timeout, and
increments `ApproximateReceiveCount` — the counter that dead-letter redrive policies
act on. Peeking repeatedly at a production queue can push a legitimate message into the
DLQ.

Prefer `get-queue-attributes` above. If you truly need the body, pass
`--visibility-timeout 0` to limit the damage, and tell the user you did it.

## Live endpoints

A Lambda Function URL or API Gateway endpoint is a real environment — the skill's "Live
endpoint" rule applies: synthetic test data, and the report names what the request
created.
