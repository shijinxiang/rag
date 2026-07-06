"""
=============================================================================
RAG Evaluation Runner
=============================================================================
Runs Ragas evaluation against the Golden Dataset.

Usage:
    python scripts/run_evaluation.py --dataset backend/data/golden_dataset/qa_pairs.json
    python scripts/run_evaluation.py --dataset qa_pairs.json --metrics hit_rate,mrr,faithfulness
    python scripts/run_evaluation.py --compare results/before.json results/after.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

# Metrics to evaluate
RETRIEVAL_METRICS = ["hit_rate", "mrr", "recall", "precision"]
GENERATION_METRICS = ["faithfulness", "answer_relevance", "context_precision", "context_recall"]
ALL_METRICS = RETRIEVAL_METRICS + GENERATION_METRICS


def load_dataset(path: str) -> list[dict]:
    """Load the Golden Dataset JSON file."""
    dataset_path = Path(path)
    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded {len(data)} Q&A pairs from {dataset_path}")
    return data


def run_evaluation(dataset: list[dict], metrics: list[str]) -> dict:
    """Run the specified metrics against the dataset."""
    print(f"\nRunning evaluation with metrics: {', '.join(metrics)}")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_size": len(dataset),
        "metrics": {},
    }

    # TODO: Implement actual Ragas evaluation in Stage 5
    for metric in metrics:
        if metric in RETRIEVAL_METRICS:
            print(f"  Computing {metric}... (placeholder)")
            results["metrics"][metric] = {"score": 0.0, "details": "Not yet implemented"}
        elif metric in GENERATION_METRICS:
            print(f"  Computing {metric}... (placeholder)")
            results["metrics"][metric] = {"score": 0.0, "details": "Not yet implemented"}

    return results


def save_results(results: dict, output_dir: str = "results"):
    """Save evaluation results to a JSON file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"eval_{timestamp}.json"
    filepath = output_path / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {filepath}")
    return filepath


def compare_runs(before_path: str, after_path: str):
    """Compare two evaluation runs and print the diff."""
    with open(before_path, "r", encoding="utf-8") as f:
        before = json.load(f)
    with open(after_path, "r", encoding="utf-8") as f:
        after = json.load(f)

    print("=" * 60)
    print("  Evaluation Comparison")
    print("=" * 60)
    print(f"  Baseline: {before_path}")
    print(f"  Current:  {after_path}")
    print("-" * 60)

    before_metrics = before.get("metrics", {})
    after_metrics = after.get("metrics", {})

    all_metric_names = set(before_metrics.keys()) | set(after_metrics.keys())

    for metric in sorted(all_metric_names):
        b_score = before_metrics.get(metric, {}).get("score", "N/A")
        a_score = after_metrics.get(metric, {}).get("score", "N/A")

        if isinstance(b_score, (int, float)) and isinstance(a_score, (int, float)):
            diff = a_score - b_score
            direction = "↑" if diff > 0 else "↓" if diff < 0 else "="
            print(f"  {metric:25s}: {b_score:.4f} → {a_score:.4f} ({direction} {abs(diff):.4f})")
        else:
            print(f"  {metric:25s}: {b_score} → {a_score}")

    print("-" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Run RAG evaluation against the Golden Dataset"
    )
    parser.add_argument(
        "--dataset", "-d",
        default="backend/data/golden_dataset/qa_pairs.json",
        help="Path to Golden Dataset JSON file",
    )
    parser.add_argument(
        "--metrics", "-m",
        default="all",
        help="Comma-separated metrics to compute, or 'all' (default: all)",
    )
    parser.add_argument(
        "--output", "-o",
        default="results",
        help="Output directory for results",
    )
    parser.add_argument(
        "--compare", "-c",
        nargs=2,
        metavar=("BEFORE", "AFTER"),
        help="Compare two evaluation result files",
    )

    args = parser.parse_args()

    if args.compare:
        compare_runs(args.compare[0], args.compare[1])
        return

    # Determine metrics
    if args.metrics == "all":
        metrics = ALL_METRICS
    else:
        metrics = [m.strip() for m in args.metrics.split(",")]

    # Validate metrics
    unknown = set(metrics) - set(ALL_METRICS)
    if unknown:
        print(f"Unknown metrics: {unknown}")
        print(f"Available: {ALL_METRICS}")
        sys.exit(1)

    # Run
    dataset = load_dataset(args.dataset)
    results = run_evaluation(dataset, metrics)
    save_results(results, args.output)


if __name__ == "__main__":
    main()
