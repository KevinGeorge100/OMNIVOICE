"""Summarize a numeric OV-006 CSV/JSON export (no raw conversation data)."""

import argparse
import csv
import json
from pathlib import Path

from omnivoice.latency import METRICS, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--output")
    args = parser.parse_args()
    path = Path(args.input)
    if path.suffix.lower() == ".json":
        rows = json.loads(path.read_text(encoding="utf-8"))
    else:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            for name in METRICS:
                row[name] = float(row[name]) if row.get(name) else None
    output = json.dumps(summarize(rows), indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
