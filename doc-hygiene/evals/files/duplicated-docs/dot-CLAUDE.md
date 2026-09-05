# CLAUDE.md

This is an opinionated Terraform module for running Valkey on AWS ElastiCache.

## Requirements

- Terraform >= 1.13
- AWS provider >= 6.0
- An existing VPC with private subnets tagged `tier = "data"`

## Usage

```hcl
module "cache" {
  source = "github.com/example/terraform-aws-cache?ref=v1.2.0"

  name    = "sessions"
  size    = "small"
  vpc_id  = module.network.vpc_id
}
```

Sizes map to node types: `small` (cache.t4g.small), `medium` (cache.m7g.large), `large` (cache.m7g.2xlarge).

## Deployment

Plans run on every pull request and applies run on merge to `main`. Both use OIDC — no long-lived AWS credentials exist in CI.

## Conventions

- Locals live in `variables.tf`. Data sources live in `main.tf`.
- Never use `jsonencode()` for IAM policy documents — use `aws_iam_policy_document` data sources.
- Run `terraform fmt`, `terraform validate`, and `tflint` before presenting any change.
- Use `moved` blocks whenever a resource label changes.
