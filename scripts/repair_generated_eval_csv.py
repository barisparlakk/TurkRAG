"""Repair blank generated-eval CSV rows from a fuller generated question export.

Usage:
  python scripts/repair_generated_eval_csv.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

TARGET_PATH = Path("eval/eval_set_generated.csv")
SOURCE_PATH = Path("eval/generated_questions.csv")
MATCH_FIELDS = ("relevant_doc", "doc_id", "chunk_index")
COPY_FIELDS = ("question", "ground_truth")


def repair_generated_eval_csv(
    target_path: str | Path = TARGET_PATH,
    source_path: str | Path = SOURCE_PATH,
) -> int:
    target = Path(target_path)
    source = Path(source_path)

    with target.open(encoding="utf-8", newline="") as handle:
        target_rows = list(csv.DictReader(handle))
    with source.open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    source_buckets: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        key = tuple(row.get(field, "") for field in MATCH_FIELDS)
        source_buckets[key].append(row)

    bucket_offsets: dict[tuple[str, ...], int] = defaultdict(int)
    repaired_count = 0
    for row in target_rows:
        if row.get("question", "").strip() and row.get("ground_truth", "").strip():
            continue
        key = tuple(row.get(field, "") for field in MATCH_FIELDS)
        candidates = source_buckets.get(key, [])
        offset = bucket_offsets[key]
        if offset >= len(candidates):
            continue
        matched = candidates[offset]
        bucket_offsets[key] += 1
        changed = False
        for field in COPY_FIELDS:
            source_value = matched.get(field, "")
            if source_value and row.get(field, "") != source_value:
                row[field] = source_value
                changed = True
        if changed:
            repaired_count += 1

    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=target_rows[0].keys())
        writer.writeheader()
        writer.writerows(target_rows)

    return repaired_count


def main() -> int:
    repaired_count = repair_generated_eval_csv()
    print(f"Repaired rows: {repaired_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
