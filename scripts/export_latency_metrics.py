"""Export completed turn metrics without transcripts, audio, or credentials."""

import argparse
import csv
import json
import sqlite3
from pathlib import Path

from omnivoice.latency import METRICS, exclusion_reason, project_turn, summarize


def export(database, *, provider=None, session=None, from_date=None, to_date=None,
           include_incomplete=False):
    clauses = ["1=1"]
    args = []
    for predicate, value in (("provider = ?", provider), ("id = ?", session),
                             ("date(started, 'unixepoch') >= ?", from_date),
                             ("date(started, 'unixepoch') <= ?", to_date)):
        if value is not None:
            clauses.append(predicate)
            args.append(value)
    rows = []
    excluded = {}
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        for call in connection.execute(
            "SELECT id, provider, status, started, ended, metrics FROM calls WHERE "
            + " AND ".join(clauses) + " ORDER BY started, id", args
        ):
            try:
                turns = json.loads(call["metrics"] or "{}").get("turns", [])
                if not isinstance(turns, list):
                    raise ValueError("turns is not a list")
            except (TypeError, ValueError, AttributeError):
                excluded["invalid_metrics"] = excluded.get("invalid_metrics", 0) + 1
                continue
            for index, turn in enumerate(turns, 1):
                if not isinstance(turn, dict):
                    excluded["invalid_turn"] = excluded.get("invalid_turn", 0) + 1
                    continue
                row = project_turn(call, turn, index)
                reason = exclusion_reason(call, row)
                if reason:
                    excluded[reason] = excluded.get(reason, 0) + 1
                if include_incomplete or reason is None:
                    rows.append(row)
    return rows, summarize(rows, excluded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="data/omnivoice.db")
    parser.add_argument("--output", required=True)
    parser.add_argument("--format", choices=("csv", "json"), default="csv")
    parser.add_argument("--provider")
    parser.add_argument("--session")
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--include-incomplete", action="store_true")
    parser.add_argument("--summary-output")
    args = parser.parse_args()
    rows, summary = export(args.database, provider=args.provider, session=args.session,
                           from_date=args.from_date, to_date=args.to_date,
                           include_incomplete=args.include_incomplete)
    target = Path(args.output)
    if args.format == "json":
        target.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    else:
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["session_id", "turn_index", "provider",
                "call_started", "path", "interrupted", "error", *METRICS])
            writer.writeheader()
            writer.writerows(rows)
    if args.summary_output:
        Path(args.summary_output).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "exclusions": summary["exclusions"]}))


if __name__ == "__main__":
    main()
