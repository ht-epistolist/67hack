#!/usr/bin/env python3
import json
import argparse
from pathlib import Path
from src.evaluator import score


def main():
    parser = argparse.ArgumentParser(
        description="Score fraud detection results against hidden answer key"
    )
    parser.add_argument(
        '--result', '-r',
        type=str,
        default='results/detection_result.json',
        help='Path to detection result JSON (default: results/detection_result.json)',
    )
    parser.add_argument(
        '--answer-key', '-k',
        type=str,
        default='answer_key.json',
        help='Path to hidden answer key JSON (default: answer_key.json)',
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Path to write evaluation report (default: print only)',
    )

    args = parser.parse_args()

    result_path = Path(args.result)
    key_path = Path(args.answer_key)

    if not result_path.exists():
        print(f"Error: result file not found: {result_path}")
        print("Run `python main.py` first to generate detection results.")
        return 1

    if not key_path.exists():
        print(f"Error: answer key not found: {key_path}")
        print("Provide the answer_key.json from event judges at this path.")
        return 1

    with open(result_path) as f:
        result = json.load(f)

    with open(key_path) as f:
        answer_key = json.load(f)

    report = score(result, answer_key)

    print("=" * 60)
    print("FRAUD DETECTION SCORING REPORT")
    print("=" * 60)
    print()
    print("Ring Member Identification:")
    print(f"  Precision: {report.ring_precision:.4f}")
    print(f"  Recall:    {report.ring_recall:.4f}")
    print(f"  F1 Score:  {report.ring_f1:.4f}")
    print()
    print("Exonerated Account Identification:")
    print(f"  Precision: {report.exonerated_precision:.4f}")
    print(f"  Recall:    {report.exonerated_recall:.4f}")
    print(f"  F1 Score:  {report.exonerated_f1:.4f}")
    print()
    print("Exposure Accuracy:")
    print(f"  Accuracy:  {report.exposure_accuracy:.4f}")
    print(f"  (Detected: ${report.details['detected_exposure']:,.2f}, "
          f"True: ${report.details['true_exposure']:,.2f})")
    print()
    print("Loop Overlap:")
    print(f"  Score:     {report.loop_overlap:.4f}")
    print(f"  (Detected: {report.details['detected_loop_count']} loops, "
          f"True: {report.details['true_loop_count']} loops)")
    print()
    print("Composite Score:")
    print(f"  Total:     {report.composite_score:.4f}")
    print()
    print("-" * 60)
    print(f"True ring members: {report.details['true_ring_count']}")
    print(f"Detected: {report.details['detected_ring_count']}")
    print(f"True exonerated: {report.details['true_exonerated_count']}")
    print(f"Detected: {report.details['detected_exonerated_count']}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nReport saved to {output_path}")

    return 0


if __name__ == '__main__':
    exit(main())
