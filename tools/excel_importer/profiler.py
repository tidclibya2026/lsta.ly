from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.excel_importer.workbook_reader import read_workbook


def _is_empty(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def profile_workbook(input_path: Path, output_dir: Path) -> None:
    workbook_data = read_workbook(input_path)

    output_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "source_file": input_path.name,
        "sheet_count": len(workbook_data),
        "sheets": {},
    }

    for sheet_name, records in workbook_data.items():
        columns = sorted(
            {
                column
                for record in records
                for column in record.keys()
            }
        )

        missing_counts = {
            column: sum(
                1
                for record in records
                if _is_empty(record.get(column))
            )
            for column in columns
        }

        duplicate_rows = 0
        if records:
            normalized_rows = [
                tuple(str(record.get(column, "")).strip() for column in columns)
                for record in records
            ]
            frequencies = Counter(normalized_rows)
            duplicate_rows = sum(
                count - 1
                for count in frequencies.values()
                if count > 1
            )

        report["sheets"][sheet_name] = {
            "row_count": len(records),
            "column_count": len(columns),
            "columns": columns,
            "missing_counts": missing_counts,
            "duplicate_rows": duplicate_rows,
        }

    output_file = output_dir / f"{input_path.stem}_profile.json"

    output_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"تم إنشاء تقرير التحليل: {output_file}")