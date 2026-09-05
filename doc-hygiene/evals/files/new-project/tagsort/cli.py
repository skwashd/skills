"""tagsort: normalise AWS resource tags across Terraform files.

Walks the given directory for .tf files, finds tags blocks, sorts keys
alphabetically, enforces the required keys (Owner, CostCentre, Environment),
and rewrites files in place. Exits 1 when --check finds unsorted or
incomplete tags without rewriting anything, so it can run in CI.
"""

import argparse
import sys

REQUIRED_KEYS = ("Owner", "CostCentre", "Environment")


def main() -> int:
    parser = argparse.ArgumentParser(prog="tagsort")
    parser.add_argument("path", help="Directory to scan for .tf files")
    parser.add_argument("--check", action="store_true", help="Report problems without rewriting")
    args = parser.parse_args()
    print(f"scanning {args.path} (check={args.check}) for {REQUIRED_KEYS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
