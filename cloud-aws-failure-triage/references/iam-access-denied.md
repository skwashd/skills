# IAM AccessDenied Playbook

## Parse the Error First

Every AccessDenied message has the same anatomy. Extract all four parts verbatim:

```
User: arn:aws:sts::123456789012:assumed-role/my-app-sfn-role/xyz
  is not authorized to perform: rds:CreateDBSnapshot
  on resource: arn:aws:rds:eu-west-1:123456789012:db:my-instance
  because no identity-based policy allows the rds:CreateDBSnapshot action
```

- **Principal** → which role. The assumed-role ARN's second segment is the role name; find where that role's policy is defined in the IaC (grep the Terraform/CDK source for the role name).
- **Action** → the one permission missing.
- **Resource** → what to scope the new statement to.
- **Trailing clause** → *why* it was denied. "no identity-based policy allows" is the simple case; "with an explicit deny" means an SCP, permission boundary, or Deny statement is overriding — adding an Allow will not help, find the deny instead. A missing clause plus a resource in another account usually means the *resource* policy (bucket policy, key policy, bus policy) is the gap.

## Make the Minimal Change

Add the single action against the properly scoped resource to the existing policy document for that role. No wildcards in Action or Resource. Match the file's existing style (aws_iam_policy_document data sources / structured statements — don't introduce `jsonencode()` into a codebase that avoids it).

Then check the same policy for siblings: an operation that needs `CreateDBSnapshot` will usually need the rest of its workflow (`CopyDBSnapshot`, `DeleteDBSnapshot`) — add the ones the code actually calls, and only those. This kills the serial whack-a-mole pattern where each deploy reveals one more missing action.

## Classic Traps

- **SSM parameter paths need two resource forms.** `GetParametersByPath` on `/apps/web/foo` requires BOTH `arn:...:parameter/apps/web/foo` AND `arn:...:parameter/apps/web/foo/*`. Granting only one produces an AccessDenied that looks identical to a missing action.
- **The resource format must match what the action requires**, not what you have. Some RDS actions authorize against the `cluster-snapshot:` or `snapshot:` ARN even though you think in terms of the instance/cluster. When the action succeeds in the console but fails in code, suspect the ARN format. Check the action's resource types in the Service Authorization Reference rather than pattern-matching.
- **KMS rides along.** Snapshot copy/share across accounts, encrypted bucket access, and encrypted log delivery all fail with the *service's* AccessDenied even when the missing grant is on the KMS key. If the resource is encrypted with a CMK, check `kms:Decrypt`/`GenerateDataKey`/`CreateGrant` on the key policy and the identity policy.
- **`logs:CreateLogGroup` denials** on first invocation: the execution role can write to a log group but not create it. Either pre-create the log group in IaC (preferred — you control retention) or grant create on the specific log-group ARN.
- **Case-sensitive API field names in Step Functions SDK integrations** (`DbSnapshotIdentifier` vs `DBSnapshotIdentifier`) produce errors that masquerade as permission/validation problems. If the policy looks right, re-check the request payload against the API's actual field casing.
- **Cross-account/eventing**: EventBridge cross-bus targets, S3→SNS, etc. authorize via *resource* policies on the receiving side. The sender's identity policy can be perfect and delivery still denied.

## Policy Validator Findings (parliament, Access Analyzer, tflint rules)

Treat findings as real until proven otherwise:

- `RESOURCE_MISMATCH` → the statement grants an action against a resource format that action can't apply to. Fix the ARN format (see traps above); don't broaden the resource.
- `RESOURCE_POLICY_PRIVILEGE_ESCALATION` / passRole findings → check whether the role can be made assumable or passable more narrowly (`iam:PassRole` with `iam:PassedToService` condition, scoped resource).
- Suppressing a finding requires a written justification in the config explaining why it's a false positive *here*. "It's noisy" is not a justification.

## Verify

Re-run the exact operation that failed (or its dry-run/read-only analogue). For Step Functions, start an execution and check it passes the previously failing state. One green execution of the failing path is the proof; a clean `terraform plan` is not.
