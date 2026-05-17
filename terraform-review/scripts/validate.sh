#!/usr/bin/env bash
# validate.sh — run the full Terraform validation workflow.
#
# Steps:
#   1. terraform fmt -recursive -check -diff   (fails if anything is unformatted)
#   2. terraform validate                       (syntax and reference checks)
#   3. tflint --init                            (downloads configured plugins)
#   4. tflint --recursive                       (runs AWS + dave-says rulesets)
#
# Prerequisites:
#   - terraform and tflint on PATH
#   - terraform init has been run in the working directory at least once
#     (otherwise `terraform validate` will fail with "Module not installed")
#
# Suitable for use as a pre-commit hook or in CI. Extra arguments are passed
# through to tflint, so you can do e.g.:
#   ./validate.sh --fix
#   ./validate.sh --format=json

set -euo pipefail

echo "==> terraform fmt -recursive -check -diff"
terraform fmt -recursive -check -diff

echo "==> terraform validate"
terraform validate

echo "==> tflint --init"
tflint --init

echo "==> tflint --recursive"
tflint --recursive "$@"

echo "✅ All checks passed."
