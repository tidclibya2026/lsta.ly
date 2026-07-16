from __future__ import annotations

import argparse
from pathlib import Path

from tools.merge_engine.engine import run_match
from tools.merge_engine.layer_config import load_layer_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LSTA Excel/KML Merge Review Engine")
    sub = parser.add_subparsers(dest="command", required=True)
    match = sub.add_parser("match-hotels", help="مطابقة طبقة الفنادق بين Excel وKML/GeoJSON")
    match.add_argument("--excel", type=Path, required=True)
    match.add_argument("--geojson", type=Path, required=True)
    match.add_argument("--output", type=Path, required=True)
    match.add_argument("--min-score", type=float, default=60.0)
    match.add_argument("--max-distance", type=float, default=1000.0)
    generic = sub.add_parser("match-layer", help="Config-driven national layer matching")
    generic.add_argument("--config", type=Path, required=True)
    generic.add_argument("--excel", type=Path, required=True)
    generic.add_argument("--geojson", type=Path, required=True)
    generic.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "match-hotels":
        summary = run_match(args.excel, args.geojson, args.output, args.min_score, args.max_distance)
        print("تم إنشاء مراجعة المطابقة دون دمج أو كتابة إلى قاعدة البيانات.")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0
    if args.command == "match-layer":
        config = load_layer_config(args.config)
        thresholds = config["distance_thresholds"]
        summary = run_match(args.excel, args.geojson, args.output, float(config["review_rules"].get("minimum_candidate_score", 65)), float(thresholds.get("maximum_candidate_meters", 1000)), layer_config=config)
        print("Matching completed for review only; no merge or promotion was performed.")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0
    return 2
