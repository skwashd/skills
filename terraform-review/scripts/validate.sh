#!/usr/bin/env bash
# validate.sh — run the full Terraform validation workflow.
#
# Steps:
#   1. terraform fmt -recursive [-check -diff]  (check mode by default)
#   2. terraform validate                       (syntax and reference checks)
#   3. tflint --init                            (downloads configured plugins)
#   4. tflint --recursive                       (runs AWS + dave-says rulesets)
#
# Works with OpenTofu too: if `terraform` is not on PATH but `tofu` is, the
# script uses `tofu`. Override explicitly with TF_BIN=tofu ./validate.sh
#
# Prerequisites:
#   - terraform (or tofu) and tflint on PATH
#   - `terraform init` / `tofu init` has been run in the working directory at
#     least once (otherwise validate fails with "Module not installed")
#
# Suitable for use as a pre-commit hook or in CI. By default nothing is
# modified: `terraform fmt` runs in -check mode and fails on unformatted files.
#
#   ./validate.sh                 # check only — safe for CI
#   ./validate.sh --fix           # rewrite formatting and apply tflint autofixes
#
# --fix is intercepted by this script rather than passed straight through,
# because `terraform fmt -check` would otherwise abort the run before tflint
# ever gets a chance to fix anything. Any other arguments are forwarded to
# tflint, so you can also do:
#
#   ./validate.sh --format=json
#   ./validate.sh --minimum-failure-severity=error
#   ./validate.sh --fix --format=compact

set -euo pipefail

# Prefer terraform; fall back to tofu. Override with TF_BIN.
if [ -z "${TF_BIN:-}" ]; then
  if command -v terraform >/dev/null 2>&1; then
    TF_BIN=terraform
  elif command -v tofu >/dev/null 2>&1; then
    TF_BIN=tofu
  else
    echo "error: neither 'terraform' nor 'tofu' found on PATH" >&2
    exit 127
  fi
fi

FIX=0
TFLINT_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --fix) FIX=1 ;;
    *) TFLINT_ARGS+=("$arg") ;;
  esac
done

if [ "$FIX" -eq 1 ]; then
  echo "==> $TF_BIN fmt -recursive (rewriting)"
  "$TF_BIN" fmt -recursive
else
  echo "==> $TF_BIN fmt -recursive -check -diff"
  "$TF_BIN" fmt -recursive -check -diff
fi

echo "==> $TF_BIN validate"
"$TF_BIN" validate

echo "==> tflint --init"
tflint --init

if [ "$FIX" -eq 1 ]; then
  echo "==> tflint --recursive --fix"
  tflint --recursive --fix ${TFLINT_ARGS[@]+"${TFLINT_ARGS[@]}"}
else
  echo "==> tflint --recursive"
  tflint --recursive ${TFLINT_ARGS[@]+"${TFLINT_ARGS[@]}"}
fi

echo "✅ All checks passed."
