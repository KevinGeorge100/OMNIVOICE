"""One-command, read-only readiness check for a controlled Vobiz PSTN demo."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omnivoice.config import Settings
from omnivoice.vobiz_preflight import run_vobiz_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--public-base", help="Current HTTPS tunnel origin; overrides stale env-file value")
    parser.add_argument("--local-base", default="http://127.0.0.1:8000")
    parser.add_argument("--line-id", help="Select one registered Vobiz line when multiple exist")
    parser.add_argument("--require-business-demo", action="store_true",
                        help="Require the marked sales fixture and line to share a tenant")
    args = parser.parse_args()
    env_file = args.env_file.expanduser().resolve()
    if not env_file.is_file():
        print("FAIL: Private env file is unavailable.")
        return 2
    try:
        settings = Settings(_env_file=env_file)
        if args.public_base:
            settings.public_base_url = args.public_base
        database = settings.database
        if not database.is_absolute():
            database = (env_file.parent / database).resolve()
        if not settings.silero_model.is_absolute():
            settings.silero_model = (env_file.parent / settings.silero_model).resolve()
        checks = run_vobiz_preflight(
            settings, database, local_base=args.local_base, line_id=args.line_id,
            require_business_demo=args.require_business_demo,
        )
    except Exception:
        print("FAIL: Preflight could not complete; no credentials were printed.")
        return 2
    for level, message in checks:
        print(f"{level}: {message}")
    print("RESULT: " + ("FAIL" if any(level == "FAIL" for level, _ in checks) else
                        "WARN" if any(level == "WARN" for level, _ in checks) else "PASS"))
    return int(any(level == "FAIL" for level, _ in checks))


if __name__ == "__main__":
    raise SystemExit(main())
