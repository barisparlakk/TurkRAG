"""Audit committed retrieval metric artifacts for obvious integrity issues.

Usage:
  python scripts/audit_retrieval_artifacts.py
  python scripts/audit_retrieval_artifacts.py --paths results/retrieval_metrics.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

DEFAULT_PATHS = (
    "results/retrieval_metrics.json",
    "results/retrieval_metrics_47q.json",
    "results/retrieval_metrics_55q.json",
)
_COUNT_SUFFIX_RE = re.compile(r"_(\d+)q\.json$")
_NORMALIZED_FIELD_NAMES = {
    "mean_mrr",
    "mean_ap",
}
_NORMALIZED_FIELD_PREFIXES = (
    "recall@",
    "precision@",
    "ndcg@",
)
_NORMALIZED_GROUP_NAMES = (
    "recall_at_k",
    "precision_at_k",
    "ndcg_at_k",
)


def _is_normalized_metric(field_name: str) -> bool:
    return field_name in _NORMALIZED_FIELD_NAMES or field_name.startswith(_NORMALIZED_FIELD_PREFIXES)


def _validate_normalized_metrics(
    metrics: dict,
    *,
    artifact_name: str,
    scope: str,
    treat_all_fields_as_normalized: bool = False,
) -> list[str]:
    issues: list[str] = []
    for field_name, value in metrics.items():
        if not treat_all_fields_as_normalized and not _is_normalized_metric(field_name):
            continue
        if not isinstance(value, (int, float)) or math.isnan(value) or not 0.0 <= value <= 1.0:
            issues.append(
                f"{artifact_name}: {scope} field '{field_name}' must be between 0 and 1, got {value!r}"
            )
    return issues


def audit_retrieval_artifact(path: str | Path) -> list[str]:
    artifact_path = Path(path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    issues: list[str] = []

    if not isinstance(payload, list):
        return [f"{artifact_path.name}: top-level JSON payload must be a list"]

    for result_index, result in enumerate(payload):
        if not isinstance(result, dict):
            issues.append(f"{artifact_path.name}: result #{result_index + 1} is not a JSON object")
            continue

        aggregate = result.get("aggregate")
        if not isinstance(aggregate, dict):
            issues.append(f"{artifact_path.name}: result #{result_index + 1} is missing aggregate metrics")
            continue

        per_query = result.get("per_query")
        if not isinstance(per_query, list):
            issues.append(f"{artifact_path.name}: result #{result_index + 1} is missing per_query rows")
            continue

        n_queries = aggregate.get("n_queries")
        if n_queries != len(per_query):
            issues.append(
                f"{artifact_path.name}: aggregate n_queries={n_queries!r} does not match {len(per_query)} per_query rows"
            )

        suffix_match = _COUNT_SUFFIX_RE.search(artifact_path.name)
        if suffix_match and isinstance(n_queries, int):
            expected_count = int(suffix_match.group(1))
            if n_queries != expected_count:
                issues.append(
                    f"{artifact_path.name}: filename implies {expected_count} queries but aggregate reports {n_queries}"
                )

        issues.extend(
            _validate_normalized_metrics(
                aggregate,
                artifact_name=artifact_path.name,
                scope=f"aggregate result #{result_index + 1}",
            )
        )

        for metric_group_name in _NORMALIZED_GROUP_NAMES:
            metric_group = aggregate.get(metric_group_name, {})
            if not isinstance(metric_group, dict):
                issues.append(
                    f"{artifact_path.name}: aggregate result #{result_index + 1} field '{metric_group_name}' must be an object"
                )
                continue
            issues.extend(
                _validate_normalized_metrics(
                    {f"{metric_group_name}.{k}": v for k, v in metric_group.items()},
                    artifact_name=artifact_path.name,
                    scope=f"aggregate result #{result_index + 1}",
                    treat_all_fields_as_normalized=True,
                )
            )

        empty_questions = 0
        for query_index, query in enumerate(per_query):
            if not isinstance(query, dict):
                issues.append(
                    f"{artifact_path.name}: per_query row #{query_index + 1} in result #{result_index + 1} is not an object"
                )
                continue
            if not str(query.get("question", "")).strip():
                empty_questions += 1
            issues.extend(
                _validate_normalized_metrics(
                    query,
                    artifact_name=artifact_path.name,
                    scope=f"per_query row #{query_index + 1}",
                )
            )
        if empty_questions:
            issues.append(
                f"{artifact_path.name}: result #{result_index + 1} contains {empty_questions} blank per_query question values"
            )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit retrieval metric artifacts for stale/broken values")
    parser.add_argument(
        "--paths",
        nargs="+",
        default=list(DEFAULT_PATHS),
        help="Artifact paths to audit (default: committed retrieval_metrics*.json files)",
    )
    args = parser.parse_args()

    all_issues: list[str] = []
    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            all_issues.append(f"{path}: file not found")
            continue
        all_issues.extend(audit_retrieval_artifact(path))

    if all_issues:
        for issue in all_issues:
            print(f"FAIL: {issue}")
        return 1

    for raw_path in args.paths:
        print(f"OK: {raw_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
