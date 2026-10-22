"""Reset only the marked synthetic demo tenant; preserve all other data."""

import argparse
from pathlib import Path

from omnivoice.demo_fixture import DEFAULT_DATABASE, prepare_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    prepare_demo(args.database, reset=True, dry_run=args.dry_run)
    print(f"RESET {'PLAN' if args.dry_run else 'PASS'}: marked synthetic tenant only")
    print("Demo bookings, actions, calls, lead, slots and FAQs will be refreshed." if args.dry_run
          else "Demo bookings/actions/calls cleared; lead, FAQs and future slots restored.")
    if args.dry_run:
        print("No changes made.")


if __name__ == "__main__":
    main()
