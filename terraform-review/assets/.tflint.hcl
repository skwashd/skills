# Starter .tflint.hcl for projects using the terraform-review skill.
# Enables tflint-ruleset-aws and tflint-ruleset-dave-says.
#
# Copy this to your repository root and run `tflint --init` to download
# the plugins. Pin the versions to whatever is current at adoption time;
# the values below were current as of writing.

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

# ---------------------------------------------------------------------------
# AWS ruleset opt-ins
# ---------------------------------------------------------------------------
# The AWS ruleset ships ~700 rules; many of the high-value ones are off by
# default. Uncomment the ones that fit your organisation's standards.

# Enforce an organisation-wide tag set on every taggable resource.
# rule "aws_resource_missing_tags" {
#   enabled = true
#   tags    = ["environment", "owner", "cost_center"]
# }

# ---------------------------------------------------------------------------
# dave-says rule configuration
# ---------------------------------------------------------------------------

# Override the default 30-day CloudWatch log retention target. Uncomment and
# set retention_days to match your organisation's retention policy.
# rule "dave_cloudwatch_log_retention" {
#   enabled        = true
#   retention_days = 14
# }

# To disable individual rules, follow the same pattern:
# rule "dave_label_min_length" {
#   enabled = false
# }
