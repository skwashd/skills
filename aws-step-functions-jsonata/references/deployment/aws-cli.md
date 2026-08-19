# Deploying with the plain AWS CLI

Emitter: `scripts/deploy/emit_cli.py`

```
python scripts/deploy/emit_cli.py \
  --asl workflow.asl.json \
  --name my-state-machine \
  --type STANDARD \
  --outdir cli/
```

Produces `cli/deploy.sh`, `cli/policy.json`, and a copy of the ASL file.

## When to use this

- One-off or throwaway deployments.
- CI pipelines without an IaC tool.
- Smoke-testing a freshly authored ASL before investing in Terraform/SAM/CDK/CFN.
- Environments that forbid IaC for policy reasons.

If the state machine is long-lived, move to real IaC so drift and audit are manageable.

## What the scaffold sets up

The `deploy.sh` script:

1. Runs `envsubst` on the ASL to fill in any `${Placeholder}` tokens from environment variables.
2. Creates (idempotently) an IAM role named `<n>-execution-role`, attaches the inferred inline policy from `policy.json`.
3. Waits ~10s for IAM eventual consistency.
4. Creates (idempotently) a log group at `/aws/vendedlogs/states/<n>` with 14-day retention.
5. Calls `create-state-machine` if it doesn't exist, or `update-state-machine` if it does.

## Running it

```
cd cli/
export ProcessingLambdaArn="arn:aws:lambda:..."
export OrdersTable="orders"
./deploy.sh
```

Each `${Placeholder}` in the ASL maps to an environment variable of the same name.

## Gotchas

**No native substitution.** `envsubst` does the work. If you need more complex templating (conditionals, numeric validation), use one of the IaC tools instead.

**`CreateStateMachine` is idempotent** only on `(name, definition, type, LoggingConfiguration, TracingConfiguration, EncryptionConfiguration)`. If all of those match, the API returns the existing ARN. Different `roleArn` or `tags` are silently ignored on re-create.

**`--type` is immutable.** To switch STANDARD ↔ EXPRESS, delete and re-create under a new name.

**Log group ARN must end in `:*`.** The script builds it correctly; don't edit that line.

**Caller needs `states:CreateStateMachine` + `iam:PassRole`.** Plus write permissions to the log group and the IAM role.

**If `policy.json` has no statements** (the ASL has no recognizable Task integrations), the emitter still generates it with logging + tracing actions. The state machine will be creatable but won't have execution permissions for any integrations — add them manually.

## Cleanup

```
aws stepfunctions list-state-machines \
  --query "stateMachines[?name=='my-state-machine'].stateMachineArn" --output text \
  | xargs -I{} aws stepfunctions delete-state-machine --state-machine-arn {}
aws iam delete-role-policy --role-name my-state-machine-execution-role --policy-name my-state-machine-inline
aws iam delete-role --role-name my-state-machine-execution-role
aws logs delete-log-group --log-group-name /aws/vendedlogs/states/my-state-machine
```
