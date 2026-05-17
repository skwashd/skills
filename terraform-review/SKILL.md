---
name: terraform-review
description: Review and generate high-quality Terraform code, with checks aligned to tflint's AWS ruleset and the dave-says custom ruleset. Use whenever the user shares, pastes, or uploads any .tf files — treat shared Terraform as an implicit request for feedback even if they don't explicitly ask. Also trigger when the user asks to write, generate, scaffold, or refactor Terraform from scratch. Covers naming, file organization, IAM, S3, VPC, CloudWatch, module design, and formatting. Guidance is primarily AWS-focused, but naming, variable hygiene, file layout, and module design apply to any provider. Trigger on any mention of Terraform, HCL, .tf files, tflint, infrastructure-as-code review, "clean up my infra code", "best practices for TF", or casual sharing like "here's my Terraform, thoughts?".
---

# Terraform Review Skill

Work through each category below and flag violations with clear explanations of *why* the pattern is problematic and how to fix it. When writing Terraform, apply these guidelines proactively so the code is clean from the start.

Many of these rules are enforced by the `dave-says` tflint plugin (`tflint-ruleset-dave-says`). Where a tflint rule exists, it's noted inline as `tflint: <rule_name>` so the user knows the check is automatable.

## How to use this skill

When reviewing Terraform code:

1. **Run tflint first if shell access is available.** `tflint --recursive` with both the AWS and dave-says rulesets configured (see Section 13) will catch most of the mechanical issues this skill describes, complete with rule names you can cite back to the user. Some findings are autofixable via `tflint --fix`.
2. **Walk the categories below** for everything tflint can't see — comment quality, the "swiss army knife" module smell, output completeness, IAM policy structure, and other architectural concerns.
3. **Group findings by severity** when reporting back: Critical, Warning, Suggestion. The full output format is described at the end of this document.

When writing or refactoring Terraform from scratch, apply these guidelines proactively rather than retrofitting them.

The two rulesets play different roles:
- **`tflint-ruleset-aws`** catches provider-specific errors and architectural issues — invalid instance types, deprecated resources, missing tags, region/AZ validation, IAM policy JSON syntax. Roughly 700 rules; many are off by default.
- **`tflint-ruleset-dave-says`** catches the style and structure issues documented in this skill — naming conventions, file organisation, deprecated S3 patterns, inline IAM/security-group rules, log retention defaults, and so on.

## 1. Resource and Data Source Naming (Labels)

The label is the second string in a resource or data source declaration — e.g. `"this"` in `resource "aws_s3_bucket" "this"`.

**Don't repeat the resource type in the label.** The type is already in the declaration. `aws_iam_role.my_role` forces readers to see `_role` twice — it adds zero information. References like `aws_iam_role.this.arn` are cleaner and shorter.
`tflint: dave_label_no_type_substring`

**Labels must use snake_case** — only lowercase letters, numbers, and underscores.
`tflint: dave_label_snake`

**Labels must be at least 3 characters**, with exceptions for well-known abbreviations like `db` and `s3`.
`tflint: dave_label_min_length`

**Naming conventions:**
- When there is only a single instance of a resource type in the module, use `this`.
- For IAM roles and policies, use the service name: `lambda`, `glue`, `ecs`, or a common abbreviation like `sfn` for Step Functions.
- For everything else, use a label that makes the resource's purpose clear without echoing the type.

**Example — bad:**
```hcl
resource "aws_iam_role" "my_role" { ... }
resource "aws_s3_bucket" "s3_bucket" { ... }
```

**Example — good:**
```hcl
resource "aws_iam_role" "lambda" { ... }
resource "aws_s3_bucket" "this" { ... }
```

## 2. Resource `name` Arguments

The `name` (or `name_prefix`) argument that becomes part of an ARN or appears in the console.

**Don't include the resource type in the name.** An IAM role named `example-role` produces the ARN `arn:aws:iam::012345678910:role/example-role` — the word "role" appears twice. Drop it.
`tflint: dave_resource_name_no_type_substring`

**Resource names must use kebab-case** — only lowercase letters, numbers, and dashes.
`tflint: dave_resource_name_kebab`

**Recommended pattern:** `<app-name>-<environment>` for most resources. For IAM roles and policies: `<app-name>-<environment>-<service>`. When multiple related resources exist (e.g. several Lambda functions): `<app-name>-<environment>-<service>-<qualifier>`.

**Use `name_prefix`** for resources that may be replaced, enabling `create_before_destroy` lifecycle rules and minimising downtime.

**Prefix all role names with `var.role_prefix`** when the module defines one (see Section 5 for the standard variable definition). This supports organisational naming conventions and avoids collisions across accounts or teams.

## 3. Comments

**Comments should explain "why", never "what".** A comment that says `# IAM Role` above an `aws_iam_role` resource is pure noise — the code already says that. Good comments capture intent that the code can't express on its own: business rules, non-obvious constraints, the reason a workaround exists. If a comment restates the syntax, delete it.

If you feel like adding section headings to a file, that's usually a signal the file has grown too large. Split it instead (see Section 4).

## 4. File Organization

**Don't put everything in `main.tf`.** Terraform reads all `.tf` files in a directory — use this to keep code well structured.

**Required files in every module:**
- `versions.tf` — provider version constraints and `terraform {}` block
- `variables.tf` — input variables (sorted alphabetically by name) `tflint: dave_variable_must_be_in_variables_file`
- `outputs.tf` — output values `tflint: dave_output_must_be_in_outputs_file`
- `main.tf` — **data sources only**, never resources. Use for global data sources like `data.aws_caller_identity.current` and `data.aws_region.current`.

**Resources go in separate files grouped by service:** `s3.tf` for S3 buckets, `network.tf` for security groups and networking, `iam.tf` for IAM resources, `lambda.tf` for Lambda functions, etc. Use descriptive filenames.

When a file exceeds ~20 resources, split it further or extract a submodule. Flag files over ~200 lines as candidates for splitting.

## 5. Variables

**Every variable should have `description` and `type`.** Without a description, anyone consuming the module has to read the implementation to understand what a variable controls — this doesn't scale. Without a complete type, Terraform can't catch invalid inputs at plan time, pushing errors to apply where they're more expensive. For complex types, define the full object structure rather than using bare `map` or `object({})` — a precise type is self-documenting and catches shape mismatches early.
`tflint: dave_variable_has_description, dave_variable_has_type`

**Sort variables alphabetically by name** in `variables.tf`. This makes them easy to find in large modules.
`tflint: dave_variable_alphabetical_order`

**Standard variables to include when relevant:**
- `role_prefix` (default: `""`) — prepended to IAM role names
- `role_permission_boundary_name` (default: `null`) — for permission boundaries
- `tags` (type: `map(string)`) — applied to all taggable resources

**Don't use `region` as a variable.** Derive it from `data.aws_region.current.region` instead. This prevents mismatches between the provider's configured region and a manually passed value.
`tflint: dave_variable_region`

**Validate inputs using data sources** in addition to `validation` blocks. For example, if a variable accepts a subnet ID, validate it exists by referencing `data.aws_subnet`.

## 6. Tagging

**Tag all resources that support tags** via a `tags` variable. Consistent tagging enables cost allocation, ownership tracking, and automated operations (like cleanup scripts that target resources by environment). The top-level module should validate that `tags` contains an `environment` key.

For resources that don't have a `name` argument but do support tags, merge the `Name` tag in:

```hcl
tags = merge(var.tags, {
  Name = "descriptive-name"
})
```

## 7. S3 Bucket Configuration

**Use separate S3 resources, not inline configuration.** Since AWS provider v4 (February 2022), S3 bucket sub-resources were split out. The inline properties on `aws_s3_bucket` are deprecated.
`tflint: dave_s3_no_inline_config (severity: ERROR)`

**Bad — deprecated inline style:**
```hcl
resource "aws_s3_bucket" "this" {
  bucket = "my-bucket"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "aws:kms"
      }
    }
  }
}
```

**Good — separate resources:**
```hcl
resource "aws_s3_bucket" "this" {
  bucket = "my-bucket"
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}
```

Flag any use of inline S3 bucket properties that have dedicated resources: `versioning`, `logging`, `server_side_encryption_configuration`, `lifecycle_rule`, `cors_rule`, `website`, `acceleration_status`, `request_payer`, `replication_configuration`, `object_lock_configuration`, `acl`/`grant`, `policy`.

**Additional S3 rules:**
- Enable access logging unless explicitly exempted. Validate the logging bucket exists with a data source — a typo in a logging target silently drops all access logs.
- Don't make buckets public or allow direct S3 website hosting. Public buckets are consistently one of the top causes of data breaches in AWS. Use CloudFront for web access — it adds caching, TLS, and access controls.
  `tflint: dave_s3_no_public_acl (severity: ERROR, fixable: replaces with "private")`

### Account Regional Namespaces

**Create all new S3 buckets in the account regional namespace.** S3 bucket names in the global namespace are first-come-first-served across all AWS accounts — this causes naming collisions, makes bucket names unpredictable across environments, and opens the door to confused-deputy attacks where another account could squat on a predictable name. Account regional namespaces guarantee that your bucket names are always available because they're scoped to your account and region.
`tflint: dave_s3_bucket_namespace`

Set `bucket_namespace = "account-regional"` and format the bucket name as `<prefix>-<account-id>-<region>-an`:

```hcl
resource "aws_s3_bucket" "this" {
  bucket           = format("%s-%s-%s-an", local.bucket_prefix, data.aws_caller_identity.current.account_id, data.aws_region.current.region)
  bucket_namespace = "account-regional"

  tags = var.tags
}
```

**Things to keep in mind:**
- `bucket_namespace` requires AWS provider **v6.37.0 or later**. Pin your provider version accordingly in `versions.tf`.
- The full bucket name (prefix + account suffix) must be between 3 and 63 characters. The account regional suffix is roughly 26 characters (e.g. `-123456789012-us-east-1-an`), so keep the prefix under ~37 characters. Longer region names like `ap-southeast-2` consume more of the budget.
- Avoid using `bucket_prefix` with `bucket_namespace = "account-regional"` — the random string that `bucket_prefix` generates combined with the account regional suffix can easily exceed the 63-character limit, leaving only ~11 characters for your actual prefix.
- This only applies to new buckets. Existing global namespace buckets can't be renamed.

### S3 Outputs

**Every module that creates S3 buckets should output `bucket_name` and `bucket_arn`.** With account regional namespaces, the final bucket name includes the account ID and region suffix, which callers can't predict from the prefix alone. Output them from the resource's computed attributes so consumers always have the resolved values:

```hcl
output "bucket_name" {
  description = "The name of the bucket."
  value       = aws_s3_bucket.this.id
}

output "bucket_arn" {
  description = "The ARN of the bucket."
  value       = aws_s3_bucket.this.arn
}
```

Use `id` for the name (not the `bucket` argument) — `id` reflects the actual created bucket name after any provider-side transformations.

## 8. IAM Policies and Roles

**Don't use `jsonencode()` for IAM policies.** It prevents reuse and clutters the code with embedded JSON. Use `aws_iam_policy_document` data sources instead.
`tflint: dave_aws_policy_no_jsonencode`

**Policy document naming conventions:**
- Same name as the role for the role's main policy
- `<service>_assume` for assume role policy documents (e.g. `lambda_assume`)
- `<service>_<resource>` when a role has multiple policies scoped to different resources

**Statement ordering within `aws_iam_policy_document`:** list `actions` first (each on its own line), then `resources`, then `conditions`. This keeps statements scannable. Omit `effect = "Allow"` since it's the default — only include `effect` when it's `"Deny"`.

**Include confused deputy conditions** in assume role policies. Without these, any resource in any AWS account could potentially assume your roles if they know the ARN — the confused deputy problem is a well-documented privilege escalation vector. At minimum, restrict by source account:

```hcl
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      identifiers = ["lambda.amazonaws.com"]
      type        = "Service"
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}
```

**Use separate resources for roles, policies, and attachments:**
- `aws_iam_role` — the role itself
- `aws_iam_policy` — the managed policy (set its `name` to match `aws_iam_role.<label>.name`)
- `aws_iam_role_policy_attachment` — binds policy to role

Prefer this over `aws_iam_role_policy`, `aws_iam_user_policy`, and `aws_iam_group_policy` (inline policies). Managed policies are reusable and visible in the IAM console's managed policies view.
`tflint: dave_iam_no_inline_policy`

**Permission boundaries:** when `var.role_permission_boundary_name` is provided, apply it using a local with a ternary:

```hcl
locals {
  permission_boundary = var.role_permission_boundary_name != null ? "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/${var.role_permission_boundary_name}" : null
}
```

## 9. CloudWatch Logs

**Create log groups explicitly** for any resource that writes to CloudWatch Logs (Lambda, ECS, API Gateway, etc.). Don't rely on the service auto-creating them — you lose control of retention and tagging.

**Set retention to 30 days** unless there's a documented compliance reason for longer. Unbounded log retention wastes money. The expected value is configurable via the `retention_days` rule attribute in `.tflint.hcl`, and the rule autofixes wrong values to the configured target.
`tflint: dave_cloudwatch_log_retention (fixable: corrects wrong values; configurable: retention_days, default 30)`

**Minimise log permissions.** Only grant `logs:CreateLogStream` and `logs:PutLogEvents`. Don't grant `logs:CreateLogGroup` — the Terraform-managed log group already exists.

## 10. VPC and Security Groups

**Derive `vpc_id` from subnets rather than accepting it as a separate variable.** Passing both `vpc_id` and `subnet_ids` creates a class of bugs where they don't match — and the error surfaces deep in the apply, not at plan time. Instead, look it up:
`tflint: dave_no_vpc_id_variable`

```hcl
data "aws_subnet" "first" {
  id = var.subnet_ids[0]
}

# Then use data.aws_subnet.first.vpc_id
```

**Validate subnet IDs** using a regex or data source lookup to catch typos early.

**Use standalone security group rule resources** — `aws_vpc_security_group_ingress_rule` and `aws_vpc_security_group_egress_rule` — instead of inline `ingress`/`egress` blocks on `aws_security_group`. This avoids rule conflicts and makes individual rules easier to manage. Create minimal access rules only.
`tflint: dave_security_group_no_inline_rules`

## 11. Module Design — Avoid "Swiss Army Knife" Modules

Modules should have opinions. A module that exposes most resource properties as variables, often with renamed arguments, provides less value than using the resources directly.

**Signs of a Swiss Army knife module:**
- Most resource arguments are exposed as variables
- Variable names differ from the underlying resource arguments for no clear reason
- The module tries to handle every possible configuration of a resource
- Complex conditional logic to enable/disable features via boolean variables

**Good modules** encode organisational decisions (security defaults, tagging standards, naming conventions) and reduce the surface area of choices a consumer needs to make.

## 12. Code Formatting

- **Separate parameter groups with empty lines** within a resource block. Grouping related parameters (e.g. identity settings, then networking, then tags) makes blocks scannable at a glance.
- **Avoid excessive alignment padding.** If aligning `=` signs requires more than 5 spaces of padding, break the parameters into groups separated by an empty line instead. Over-aligned blocks create noisy diffs when a longer parameter name is added.
- **Each list item on its own line with a trailing comma.** This produces one-line-per-change diffs, making PRs much easier to review.
- **Run `terraform fmt -recursive`** before all commits to keep formatting debates out of code review.

## 13. Validation Workflow

A starter config is bundled with this skill at `assets/.tflint.hcl`, and a runnable workflow script at `scripts/validate.sh`. Copy them into your repository to get going — the script wraps the four steps below.

Before committing, run these checks in order:

```bash
terraform fmt -recursive
terraform validate
tflint --init       # one-time, downloads configured plugins
tflint --recursive
```

`terraform fmt` ensures consistent formatting. `terraform validate` catches syntax and reference errors. `tflint` runs both the AWS and dave-says rulesets configured below. Use `tflint --fix` to auto-correct fixable issues — currently the public S3 ACL rule (`dave_s3_no_public_acl`) and the CloudWatch retention rule (`dave_cloudwatch_log_retention`).

Configure both plugins in `.tflint.hcl`:

```hcl
plugin "aws" {
  enabled = true
  version = "0.47.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

plugin "dave-says" {
  enabled = true
  version = "0.3.0"
  source  = "github.com/skwashd/tflint-ruleset-dave-says"
}

# Optional: override the default 30-day CloudWatch retention.
# rule "dave_cloudwatch_log_retention" {
#   enabled        = true
#   retention_days = 14
# }
```

### AWS ruleset rules worth enabling

The AWS ruleset ships with ~700 rules; many of the best-practice ones are off by default. The highest-value ones to enable on top of the defaults:

- **`aws_resource_missing_tags`** — enforces an organisation-wide tag set on every taggable resource. Configure with the `tags` attribute (e.g. `tags = ["environment", "owner", "cost_center"]`).
- **Deprecated-resource rules** — `aws_*_deprecated_*` rules flag resource types or arguments AWS has retired. These are easy wins and prevent breakage at apply time.
- **`aws_iam_policy_*_arn`** — validates IAM ARN formats against the AWS schema.
- **Region and AZ validation** — `aws_instance_invalid_*`, `aws_*_invalid_type` rules catch typos against the live AWS API rather than waiting for apply.

See the `tflint-ruleset-aws` rules documentation for the full catalogue and how to enable individual rules.

## Review Output Format

When reviewing Terraform, organise findings by severity:

1. **Critical** — Deprecated syntax that will break in future provider versions (e.g. inline S3 properties), security issues (public buckets, overly broad IAM permissions, missing confused deputy conditions)
2. **Warning** — Anti-patterns that hurt maintainability (e.g. `jsonencode()` policies, poor file organization, redundant naming, missing variable descriptions, inline security group rules)
3. **Suggestion** — Style improvements (e.g. comment cleanup, label naming tweaks, variable ordering, formatting alignment)

For each finding, state:
- What the issue is
- Why it matters
- How to fix it (with a code example when helpful)
- The tflint rule name if one exists, so the user knows the check is automatable
