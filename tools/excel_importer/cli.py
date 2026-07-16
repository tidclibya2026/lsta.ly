from __future__ import annotations

import argparse
from pathlib import Path

from tools.excel_importer.profiler import profile_workbook


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LSTA Excel Data Intake & Profiling Tool"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    profile_parser = subparsers.add_parser(
        "profile",
        help="تحليل ملف Excel وإنتاج تقرير جودة أولي",
    )
    profile_parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="مسار ملف Excel",
    )
    profile_parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="مجلد التقارير",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "profile":
        profile_workbook(
            input_path=args.input,
            output_dir=args.output,
        )
        return 0

    parser.error("أمر غير مدعوم")
    return 2