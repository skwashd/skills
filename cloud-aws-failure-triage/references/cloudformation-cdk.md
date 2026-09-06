# CloudFormation / CDK Deploy Failure Playbook

## First Moves (Always)

```bash
aws cloudformation describe-stack-events --stack-name <stack> \
  --query 'StackEvents[?contains(ResourceStatus, `FAILED`)].[LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
  --output table
```

The **first** FAILED event is the cause; everything after it is rollback noise. CDK's console output truncates `ResourceStatusReason` — the full reason from stack events frequently contains the answer verbatim.

For CDK, reproduce cheaply before touching AWS: `cdk synth` catches template-level errors, `cdk diff` shows what a deploy would actually do. If synth output looks stale or inconsistent, delete `cdk.out/` — a stale asset/manifest cache produces ghost errors and "no changes" lies.

## Playbooks

### DELETE_FAILED / "resource is in use"

Something outside the stack still references the resource. Don't force-delete; find the referrer:

- ACM certificate: `aws acm describe-certificate --certificate-arn <arn> --query 'Certificate.InUseBy'` — the listener/distribution still holding it must release it first (or be updated to a new cert before the old one is removed — create-before-destroy ordering).
- Security groups: search ENIs — `aws ec2 describe-network-interfaces --filters Name=group-id,Values=<sg-id>`.
- Route 53: records added outside the stack (or by a controller) block hosted-zone deletion; list and identify orphans before removing.

The general pattern: reference-holding resources must be re-pointed *before* the referenced resource can go. When CloudFormation can't sequence that within one update, split into two deploys.

### UPDATE_ROLLBACK_COMPLETE Loops / Stack Stuck

- `ROLLBACK_COMPLETE` on a *create* means the stack must be deleted before retrying — but check for retained resources first.
- For updates that keep failing on one resource, consider `--disable-rollback` during iteration (dev only) to stop paying the rollback tax per attempt.

### Stack Surgery Without Losing Stateful Resources

When a stack is wedged but contains resources that must survive (Cognito user pool, DynamoDB table, RDS):

1. Set `DeletionPolicy: Retain` / `RemovalPolicy.RETAIN` on the stateful resources and deploy that first.
2. Then restructure/delete the stack — the retained resources orphan instead of dying.
3. Re-adopt them: CloudFormation import (`cdk import`), or reference them as existing resources (`fromXxxArn`/`fromLookup`).

Never let a debugging plan put a stateful resource on the delete path, even "temporarily".

### "No changes to deploy" When You Expected Changes

- Stale `cdk.out` (delete it), or you edited a file the app doesn't actually import, or the change lives in an asset whose hash didn't change (Docker build cache, bundling).
- For Lambda code changes not deploying: confirm the asset hash changed in `cdk diff`; if not, the bundling step isn't seeing your change.

### "Unable to fetch parameters [...] from parameter store"

The synth/deploy-time lookup failed: the SSM parameter doesn't exist in *that account/region*, or the deploy role can't read it. Check region and account of the current credentials first — this error is very often "right code, wrong account". Create the parameter in IaC rather than by hand where possible.

### Lambda `Runtime.ImportModuleError` / `unable to import module`

The package deployed is missing a module or contains a wrong-architecture binary:

1. Identify the missing module from the error — is it your code (packaging path wrong) or a dependency (bundling wrong)?
2. Native dependencies (cryptography, pydantic-core, numpy) must be built for the Lambda's architecture. An arm64 function needs arm64 wheels — building on an x86 machine without a target platform flag ships the wrong binaries and imports fail only at runtime.
3. Fix in the bundling configuration (CDK bundling with the matching-arch build image, `--platform` pip flags), never by switching the function back to x86 silently, and not by hand-editing the zip.
4. Verify: invoke the function once after deploy. Import errors are invisible until invocation.

### Custom Resources / Providers Hanging for an Hour

A custom resource that never signals leaves the stack IN_PROGRESS until timeout. Find the provider Lambda's logs — the exception that prevented the signal is there.

## Verify the Fix

After redeploy: confirm the stack reaches `*_COMPLETE`, then probe the actual behaviour that failed — invoke the function, resolve the DNS name (`nslookup`), curl the endpoint, start the state machine. A completed deploy of a wrong fix is the most expensive kind of green.
