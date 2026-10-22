"""Read-only OmniVoice final-demo readiness report."""

import argparse
from pathlib import Path

from omnivoice.demo_fixture import DEFAULT_DATABASE
from omnivoice.demo_preflight import run_preflight


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--server-url", default="http://127.0.0.1:8000")
    parser.add_argument("--carrier", choices=("loopback", "exotel", "kookoo"), default="loopback")
    parser.add_argument("--skip-server", action="store_true")
    args = parser.parse_args()
    checks = run_preflight(args.database, server_url=args.server_url,
                           carrier=args.carrier, skip_server=args.skip_server)
    for level, message in checks:
        print(f"{level}: {message}")
    raise SystemExit(1 if any(level == "FAIL" for level, _ in checks) else 0)


if __name__ == "__main__":
    main()
