from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .main import run_import


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="المستورد التجريبي لملفات KML — منصة LSTA")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", default=Path("data/processed/kml"), type=Path)
    parser.add_argument("--report", type=Path, help="مسار تقرير الجودة (متوافق مع الصيغة السابقة)")
    parser.add_argument("--report-dir", default=Path("reports/kml-import"), type=Path, help="مجلد التقارير")
    parser.add_argument("--source-id", default="SRC-2026-00001")
    parser.add_argument("--feature-prefix", default="LSTA-OLD-TRIPOLI")
    parser.add_argument("--basename", default="old_tripoli")
    return parser


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "import":
        arguments = arguments[1:]
    args = build_parser().parse_args(arguments)
    report = args.report or args.report_dir / f"{args.basename}_quality_report.md"
    result, paths = run_import(args.input, args.output, report, args.source_id, args.feature_prefix, args.basename)
    manifest = result.manifest
    print(f"اكتمل الاستيراد: {manifest.feature_count} عنصر، {manifest.image_count} صورة، الحالة: {manifest.status}")
    for path in paths:
        print(path)
    return 0
