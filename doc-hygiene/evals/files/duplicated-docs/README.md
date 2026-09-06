# Terraform AWS Cache Module

An opinionated Terraform module for running Valkey on AWS ElastiCache.

## Why This Module

Most cache modules expose every ElastiCache argument as a variable. This one has an opinion: encryption on, minor version upgrades on, and t-shirt sizes instead of instance classes. If you need a knob this module does not expose, this is not the module for you.

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

<!-- BEGIN_TF_DOCS -->
## Providers

| Name | Version |
|------|---------|
| aws | >= 6.0 |

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| name | Name of the cache cluster | `string` | n/a |
| size | T-shirt size: small, medium, large | `string` | `"small"` |
| vpc_id | VPC to deploy into | `string` | n/a |

## Outputs

| Name | Description |
|------|-------------|
| endpoint | Primary endpoint address |
<!-- END_TF_DOCS -->
