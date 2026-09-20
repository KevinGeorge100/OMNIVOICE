"""Score user-supplied Fisher/FD-Bench run records; never fabricate corpus results."""

import argparse
import json
import math
import re
from pathlib import Path


def words(text):
    return re.findall(r"\w+", text.casefold())


def edit_distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, source in enumerate(reference, 1):
        current = [i]
        for j, target in enumerate(hypothesis, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (source != target)))
        previous = current
    return previous[-1]


def percentile(values, quantile):
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)] if values else None


def evaluate(records):
    errors, reference_count = 0, 0
    latency, interrupts = [], []
    false_interruptions, negative_events, missed_interruptions, positive_events = 0, 0, 0, 0
    for row in records:
        reference, hypothesis = words(row["reference"]), words(row["hypothesis"])
        errors += edit_distance(reference, hypothesis)
        reference_count += len(reference)
        for key, output in (
            ("end_of_speech_to_first_audio_ms", latency),
            ("barge_in_decision_to_clear_ms", interrupts),
        ):
            value = row.get(key)
            if value is not None:
                if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError("Timing measurements must be finite, nonnegative numbers")
                output.append(value)
        if "should_interrupt" in row and "did_interrupt" in row:
            if row["should_interrupt"]:
                positive_events += 1
                missed_interruptions += not row["did_interrupt"]
            else:
                negative_events += 1
                false_interruptions += bool(row["did_interrupt"])
    return {
        "samples": len(records),
        "reference_words": reference_count,
        "word_error_rate": errors / reference_count if reference_count else None,
        "ttfa_ms": {
            "samples": len(latency),
            "p50": percentile(latency, 0.5),
            "p95": percentile(latency, 0.95),
            "p99": percentile(latency, 0.99),
        },
        "interruption_dispatch_ms": {"samples": len(interrupts), "p95": percentile(interrupts, 0.95)},
        "false_interruption_rate": false_interruptions / negative_events if negative_events else None,
        "missed_interruption_rate": missed_interruptions / positive_events if positive_events else None,
        "note": "Metrics describe supplied run records only. No corpus or PSTN certification is implied.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("records", type=Path, help="JSONL annotated evaluation records")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    records = [
        json.loads(line) for line in args.records.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    report = json.dumps(evaluate(records), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
