# Deploying with Terraform

Emitter: `scripts/deploy/emit_terraform.py`

```
python scripts/deploy/emit_terraform.py \
  --asl workflow.asl.json \
  --name my-state-machine \
  --type STANDARD \
  --outdir terraform/
```

Produces `terraform/state_machine.tf` and a copy of the ASL file.

## What the scaffold sets up

- `aws_sfn_state_machine` with `definition = templatefile(...)` so `${Placeholder}` tokens in the ASL resolve from Terraform values.
- `aws_cloudwatch_log_group` named `/aws/vendedlogs/states/<name>` with 14-day retention.
- `aws_iam_role` with trust policy for `states.amazonaws.com`.
- `aws_iam_role_policy` with actions inferred from Task `Resource` ARNs, plus the CloudWatch Logs and X-Ray actions required for logging and tracing.
- Logging at `ALL` + `IncludeExecutionData` + tracing enabled.

## Gotchas

**`log_destination` must end in `:*`.** Without it, apply fails with `InvalidLoggingConfiguration`. The scaffold already includes this; leave it.

**`type` is immutable.** Changing STANDARD ↔ EXPRESS requires resource replacement (new ARN). Plan for the migration.

**Definition diffs look noisy.** Terraform diffs the rendered ASL string, so whitespace changes appear as drift. Use `terraform apply -refresh-only` before meaningful changes to normalize.

**Registry docs still wrongly say `logging_configuration` is Express-only (#37827).** It works on STANDARD.

**Distributed Map self-execution permissions aren't auto-added.** If your state machine uses Distributed Map, add a separate statement allowing `states:StartExecution`, `states:DescribeExecution`, `states:StopExecution`, `states:RedriveExecution` on `aws_sfn_state_machine.this.arn`.

## Filling in placeholders

The emitter scans the ASL for `${Placeholder}` tokens and lists them. Fill each into the `templatefile()` block:

```hcl
definition = templatefile("${path.module}/workflow.asl.json", {
  ProcessingLambdaArn = aws_lambda_function.proc.arn
  OrdersTable          = aws_dynamodb_table.orders.name
})
```

## Scoping the IAM policy

The emitted policy uses `"Resource": "*"` for every statement — a safe default that always works but over-privileges. Tighten by:

- Replacing `"*"` in Lambda-invoke statements with specific function ARNs.
- Replacing `"*"` in DynamoDB statements with specific table ARNs.
- Restricting `iam:PassRole` to the specific role ARN being passed.

## Running it

```
cd terraform/
terraform init
terraform plan
terraform apply
```
