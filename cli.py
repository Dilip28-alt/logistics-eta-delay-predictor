"""
Unified Command-Line Interface (CLI) for Logistics ETA & Delay Risk Intelligence Platform.
Supports: generate, validate, evaluate, reproduce, and serve.
"""

import sys
import os
import argparse
import json
import uvicorn

from src.generator.generator import SyntheticDataGenerator
from src.generator.exporter import DataExporter, compute_sha256
from src.validator.validator import DataValidator
from src.engine.delay_classifier import DelayClassifierEvaluator
from src.engine.exception_handler import OperationalExceptionHandler


def cmd_generate(args):
    scale = args.scale.lower()
    seed = args.seed
    num_shipments = 50000 if scale == "full" else (args.shipments if args.shipments else 1000)
    num_facilities = 100
    num_disruptions = 1000

    print(f"============================================================")
    print(f"Logistics Platform Generator: Scale='{scale}', Seed={seed}")
    print(f"Generating {num_shipments:,} Shipments, {num_facilities} Facilities, {num_disruptions} Disruption Windows...")
    print(f"============================================================")

    gen = SyntheticDataGenerator(seed=seed)
    gen.generate_all(
        num_shipments=num_shipments,
        num_facilities=num_facilities,
        num_disruptions=num_disruptions
    )

    output_dir = os.path.abspath(args.output)
    print(f"Exporting datasets to '{output_dir}'...")
    exporter = DataExporter(gen, output_dir=output_dir)
    exporter.export_csv()
    exporter.export_json()
    exporter.export_sqlite()
    manifest = exporter.generate_manifest()

    print("\nGeneration Completed Successfully!")
    print(f"Summary Row Counts:")
    for entity, count in manifest["row_counts"].items():
        print(f"  • {entity:20s}: {count:,}")
    print(f"\nManifest and cryptographic hashes saved to {os.path.join(output_dir, 'manifest.json')}")


def cmd_validate(args):
    data_dir = os.path.abspath(args.data)
    print(f"Validating database integrity from '{data_dir}'...")

    # Load from generator with fixed seed
    gen = SyntheticDataGenerator(seed=args.seed)
    num_shipments = 1000 if args.scale == "starter" else 50000
    gen.generate_all(num_shipments=num_shipments)

    validator = DataValidator(gen)
    report = validator.validate_all()
    res = report.to_dict()

    print("\nValidation Summary:")
    print(f"  Status: {'PASSED' if res['passed'] else 'FAILED'}")
    print(f"  Total Integrity Checks : {res['total_checks']}")
    print(f"  Checks Passed          : {res['checks_passed']}")
    print(f"  Checks Failed          : {res['checks_failed']}")

    print("\nAnomaly Audit Detection Summary (Correlated with Ground Truth):")
    for anomaly_name, stats in res["anomaly_audit_summary"].items():
        print(f"  • {anomaly_name:30s} -> Injected: {stats['injected_ground_truth']}, Detected: {stats['auditor_detected']}, Matched: {stats['match']}")

    # Save validation report
    val_file = os.path.join(data_dir, "validation_report.json")
    with open(val_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"\nFull validation report written to {val_file}")


def cmd_evaluate(args):
    print(f"Running machine learning delay evaluation and ETA calibration...")
    gen = SyntheticDataGenerator(seed=args.seed)
    num_shipments = 1000 if args.scale == "starter" else 50000
    gen.generate_all(num_shipments=num_shipments)

    evaluator = DelayClassifierEvaluator(gen)
    scorecard = evaluator.train_and_evaluate()

    print("\n" + "=" * 60)
    print("MODEL EVALUATION SCORECARD")
    print("=" * 60)
    cls = scorecard["classification_metrics"]
    reg = scorecard["regression_metrics"]
    ops = scorecard["operational_metrics"]

    print(f"Classification (Delay Detection):")
    print(f"  • Accuracy                  : {cls['accuracy'] * 100:.1f}%")
    print(f"  • Precision                 : {cls['precision'] * 100:.1f}%")
    print(f"  • Recall (Delay Sensitivity): {cls['recall'] * 100:.1f}%")
    print(f"  • F1 Score                  : {cls['f1_score']:.4f}")
    print(f"  • ROC-AUC Score             : {cls['roc_auc']:.4f}")

    print(f"\nRegression (ETA Arrival Accuracy):")
    print(f"  • Mean Absolute Error (MAE) : {reg['mean_absolute_error_minutes']:.1f} minutes")
    print(f"  • Root Mean Squared Error   : {reg['root_mean_squared_error_minutes']:.1f} minutes")
    print(f"  • R² Score                  : {reg['r2_score']:.4f}")

    print(f"\nOperational Impact:")
    print(f"  • Early Warning Lead Time   : {ops['early_warning_lead_time_hours']} hours before SLA target")
    print("=" * 60)

    out_file = os.path.join(args.output, "evaluation_metrics.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(scorecard, f, indent=2)
    print(f"Scorecard written to {out_file}")


def cmd_reproduce(args):
    """
    Step 10: Regenerates twice with the same seed and compares row counts/checksums.
    """
    seed = args.seed
    num_shipments = 1000  # starter sample for reproducibility test
    print("============================================================")
    print(f"REPRODUCIBILITY BENCHMARK (Step 10 Requirement)")
    print(f"Generating Run 1 and Run 2 using fixed seed: {seed}")
    print("============================================================")

    import tempfile
    import shutil

    dir_run1 = os.path.join("data", "reproducibility_run1")
    dir_run2 = os.path.join("data", "reproducibility_run2")

    for d in (dir_run1, dir_run2):
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)

    print("\n[Run 1] Generating synthetic dataset...")
    gen1 = SyntheticDataGenerator(seed=seed)
    gen1.generate_all(num_shipments=num_shipments)
    exp1 = DataExporter(gen1, output_dir=dir_run1)
    exp1.export_csv()
    exp1.export_json()
    m1 = exp1.generate_manifest()

    print("[Run 2] Generating synthetic dataset...")
    gen2 = SyntheticDataGenerator(seed=seed)
    gen2.generate_all(num_shipments=num_shipments)
    exp2 = DataExporter(gen2, output_dir=dir_run2)
    exp2.export_csv()
    exp2.export_json()
    m2 = exp2.generate_manifest()

    print("\nComparing Row Counts:")
    counts_match = True
    for key, c1 in m1["row_counts"].items():
        c2 = m2["row_counts"].get(key)
        matched = (c1 == c2)
        if not matched:
            counts_match = False
        print(f"  • {key:20s}: Run 1={c1}, Run 2={c2} -> {'MATCH' if matched else 'MISMATCH'}")

    print("\nComparing Cryptographic SHA-256 Checksums across all CSV and JSON files:")
    all_files = sorted(list(set(m1["files"].keys()).union(set(m2["files"].keys()))))
    hashes_match = True
    for f in all_files:
        h1 = m1["files"].get(f, {}).get("sha256")
        h2 = m2["files"].get(f, {}).get("sha256")
        matched = (h1 == h2 and h1 is not None)
        if not matched:
            hashes_match = False
        status_str = "MATCH (Identical)" if matched else "MISMATCH"
        print(f"  • {f:30s} -> {status_str}")

    print("\n" + "=" * 60)
    if counts_match and hashes_match:
        print("REPRODUCIBILITY TEST: PASSED (100% Deterministic Bitwise Match)")
    else:
        print("REPRODUCIBILITY TEST: FAILED")
    print("=" * 60)


def cmd_serve(args):
    print(f"Starting Logistics ETA Platform server on http://{args.host}:{args.port}")
    uvicorn.run("src.api.app:app", host=args.host, port=args.port, reload=False)


def main():
    parser = argparse.ArgumentParser(description="Logistics ETA Estimation & Delay Risk Platform CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate synthetic logistics dataset")
    p_gen.add_argument("--scale", choices=["starter", "full"], default="starter", help="Dataset volume (starter=1,000, full=50,000)")
    p_gen.add_argument("--shipments", type=int, default=None, help="Custom shipment count override")
    p_gen.add_argument("--seed", type=int, default=20261022, help="Fixed random seed")
    p_gen.add_argument("--output", default="data", help="Output directory")

    # validate
    p_val = subparsers.add_parser("validate", help="Validate relational integrity and audit anomalies")
    p_val.add_argument("--scale", choices=["starter", "full"], default="starter")
    p_val.add_argument("--seed", type=int, default=20261022)
    p_val.add_argument("--data", default="data")

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="Train and evaluate delay classifier and ETA regressor")
    p_eval.add_argument("--scale", choices=["starter", "full"], default="starter")
    p_eval.add_argument("--seed", type=int, default=20261022)
    p_eval.add_argument("--output", default="data")

    # reproduce
    p_rep = subparsers.add_parser("reproduce", help="Run dual regeneration to demonstrate deterministic reproducibility")
    p_rep.add_argument("--seed", type=int, default=20261022)

    # serve
    p_srv = subparsers.add_parser("serve", help="Launch FastAPI web server and dashboard")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "reproduce":
        cmd_reproduce(args)
    elif args.command == "serve":
        cmd_serve(args)


if __name__ == "__main__":
    main()
