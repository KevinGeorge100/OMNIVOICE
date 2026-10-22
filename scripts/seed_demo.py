"""Create an isolated OmniVoice sales demo database; no provider calls."""

import argparse
from pathlib import Path

from omnivoice.demo_fixture import DEFAULT_DATABASE, prepare_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = prepare_demo(args.database, dry_run=args.dry_run)
    print(f"{result['operation'].upper()}: synthetic demo fixture; database={args.database}")
    if result["dry_run"]:
        print("No changes made.")
    elif result["operation"] == "exists":
        print("Fixture already exists. Use reset_demo.py to refresh its slots and clear demo state.")
    else:
        print("Approved FAQs: 6; synthetic leads: 1; future slots: 3. No carrier line created.")


if __name__ == "__main__":
    main()
