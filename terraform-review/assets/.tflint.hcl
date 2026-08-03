# Starter .tflint.hcl for projects using the terraform-review skill.
# Enables tflint-ruleset-aws and tflint-ruleset-dave-says.
#
# Copy this to your repository root and run `tflint --init` to download
# the plugins. Pin the versions to whatever is current at adoption time;
# the values below were current as of writing.

plugin "aws" {
  enabled = true
  version = "0.48.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

plugin "dave-says" {
  enabled = true
  version = "0.4.0"
  source  = "github.com/skwashd/tflint-ruleset-dave-says"
}

# If `tflint --init` panics while verifying plugin attestations, unset
# GITHUB_TOKEN or add `signature = "pgp"` to the affected plugin block.

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

# dave_list_alphabetical_order is a NO-OP until you name the attributes it
# applies to. There is no universally-correct set of lists to sort, so naming
# an attribute here asserts that its element order is not semantically
# significant. Uncomment and extend to suit.
# rule "dave_list_alphabetical_order" {
#   enabled          = true
#   attributes       = ["actions", "resources", "subnet_ids"]
#   case_insensitive = false
# }

# To disable individual rules, follow the same pattern:
# rule "dave_label_min_length" {
#   enabled = false
# }

# ---------------------------------------------------------------------------
# Adopting this in an existing codebase
# ---------------------------------------------------------------------------
# Turning both rulesets on at once in a large repo will produce a long backlog.
# Rather than disabling rules, run CI with:
#
#   tflint --recursive --minimum-failure-severity=error
#
# That reports every finding but only fails the build on errors. Tighten to
# `warning` once the backlog is cleared, so the rules stay visible throughout
# instead of being switched off and forgotten.
