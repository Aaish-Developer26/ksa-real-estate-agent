"""Orchestrates the Ragas evaluation suite across all agent datasets.

This is the entry point CI/CD calls. Exits with code 1 if any metric
falls below its threshold:
    python -m evals.runner
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.judges.faithfulness import FaithfulnessJudge
from evals.judges.relevance import AnswerRelevanceJudge
from src.core.logging_setup import get_logger, setup_logging

logger = get_logger(__name__)

DATASETS_DIR: Path = Path(__file__).parent / "datasets"
REPORTS_DIR: Path = Path(__file__).parent / "reports"

EVAL_PLAN: list[dict[str, Any]] = [
    {
        "dataset_file": "cleaning_eval_dataset.json",
        "judge": "faithfulness",
        "label": "cleaning_faithfulness",
    },
    {
        "dataset_file": "analyst_eval_dataset.json",
        "judge": "faithfulness",
        "label": "analyst_faithfulness",
    },
    {
        "dataset_file": "analyst_eval_dataset.json",
        "judge": "answer_relevance",
        "label": "analyst_relevance",
    },
    {
        "dataset_file": "risk_eval_dataset.json",
        "judge": "faithfulness",
        "label": "risk_faithfulness",
    },
]


def load_dataset(filename: str) -> list[dict[str, Any]]:
    """Load eval records from a JSON dataset file.

    Args:
        filename: JSON filename in the evals/datasets/ directory.

    Returns:
        List of record dicts from the "records" key.

    Raises:
        FileNotFoundError: If the dataset file does not exist.
        KeyError: If the "records" key is missing from the JSON.
    """
    path = DATASETS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = data["records"]
    return records


def _evaluate_entry(
    entry: dict[str, Any],
    faithfulness_judge: FaithfulnessJudge,
    relevance_judge: AnswerRelevanceJudge,
) -> dict[str, Any]:
    """Run a single EVAL_PLAN entry against the correct judge.

    Args:
        entry: One EVAL_PLAN dict with dataset_file, judge, and label.
        faithfulness_judge: Shared FaithfulnessJudge instance.
        relevance_judge: Shared AnswerRelevanceJudge instance.

    Returns:
        The judge's evaluation result dict for this entry.
    """
    records = load_dataset(entry["dataset_file"])
    if entry["judge"] == "faithfulness":
        return faithfulness_judge.evaluate_dataset(records, entry["label"])
    return relevance_judge.evaluate_dataset(records, entry["label"])


def run_evaluation_suite() -> dict[str, Any]:
    """Execute the full evaluation suite against all datasets.

    Runs all entries in EVAL_PLAN sequentially and computes the
    overall pass/fail status.

    Returns:
        Complete evaluation report dict with run_id, timestamp,
        overall_status, thresholds, results, failed_metrics, and
        details keys.
    """
    faithfulness_judge = FaithfulnessJudge()
    relevance_judge = AnswerRelevanceJudge()

    results: dict[str, float] = {}
    details: list[dict[str, Any]] = []
    for entry in EVAL_PLAN:
        result = _evaluate_entry(entry, faithfulness_judge, relevance_judge)
        results[entry["label"]] = result["score"]
        details.append(result)

    failed_metrics = [detail["dataset_name"] for detail in details if not detail["passed"]]
    overall_status = "PASS" if not failed_metrics else "FAIL"

    return {
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "thresholds": {
            "faithfulness": FaithfulnessJudge.THRESHOLD,
            "answer_relevance": AnswerRelevanceJudge.THRESHOLD,
        },
        "results": results,
        "failed_metrics": failed_metrics,
        "details": details,
    }


def save_report(report: dict[str, Any]) -> Path:
    """Save the evaluation report to the evals/reports/ directory.

    Args:
        report: Full evaluation report dict.

    Returns:
        Path to the saved report file.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORTS_DIR / f"eval_report_{timestamp}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def _print_summary(report: dict[str, Any], report_path: Path) -> None:
    """Print a human-readable evaluation summary to stdout.

    Args:
        report: Full evaluation report dict.
        report_path: Path the report was saved to.
    """
    lines = [
        "═══════════════════════════════════════════",
        f"RAGAS EVALUATION SUITE — {report['timestamp']}",
        "═══════════════════════════════════════════",
        f"Overall Status: {report['overall_status']}",
        "",
        "Metric Results:",
    ]
    for detail in report["details"]:
        status = "PASS" if detail["passed"] else "FAIL"
        lines.append(
            f"  {detail['dataset_name']}:  {detail['score']:.2f}  "
            f"[{status} ≥{detail['threshold']}]"
        )
    failed = report["failed_metrics"]
    lines.append("")
    lines.append(f"Failed metrics: {'none' if not failed else ', '.join(failed)}")
    lines.append(f"Report saved: {report_path}")
    lines.append("═══════════════════════════════════════════")
    print("\n".join(lines))


def main() -> None:
    """Entry point for the evaluation runner.

    Runs the full suite, saves the report, prints a summary, and
    exits with code 1 if overall_status == "FAIL".
    """
    setup_logging()
    logger.info("Starting Ragas evaluation suite")

    report = run_evaluation_suite()
    report_path = save_report(report)
    _print_summary(report, report_path)

    if report["overall_status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
