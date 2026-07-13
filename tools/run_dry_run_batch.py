#!/usr/bin/env python3
"""Run dry-run quality checks for all Atlas Excel layers.

The command never writes to production or staging. It executes the existing
import tool in dry-run mode, aggregates results, and emits JSON/CSV reports
for human review.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LayerJob:
    layer: str
    file: Path


def execute_job(job: LayerJob, mapping: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        "tools/import_atlas_xlsx.py",
        str(job.file),
        "--layer",
        job.layer,
        "--mapping",
        str(mapping),
        "--dry-run",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return {
            "layer": job.layer,
            "file": job.file.name,
            "status": "failed",
            "returncode": completed.returncode,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }
    payload = json.loads(completed.stdout)
    payload["status"] = "completed"
    return payload


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    columns = ["layer", "file", "sheet", "rows", "issues", "sha256", "dry_run", "status", "error"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dry-run checks for all Atlas XLSX layers.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated"))
    parser.add_argument("--mapping", type=Path, default=Path("data/mappings/atlas_layers_v1.yml"))
    args = parser.parse_args()

    jobs = [
        LayerJob("hotels", args.input_dir / "أطلس_ليبيا_السياحي_2026_طبقة_الفنادق.xlsx"),
        LayerJob("resorts_villages", args.input_dir / "أطلس_ليبيا_السياحي_2026_طبقة_القرى_والمنتجعات_السياحية.xlsx"),
        LayerJob("restaurants", args.input_dir / "أطلس_ليبيا_السياحي_2026_طبقة_المطاعم.xlsx"),
        LayerJob("cafes", args.input_dir / "أطلس_ليبيا_السياحي_2026_طبقة_المقاهي.xlsx"),
        LayerJob("thematic_layers", args.input_dir / "أطلس_ليبيا_السياحي_2026_طبقات_منفصلة_حسب_المحاور.xlsx"),
    ]

    missing = [str(job.file) for job in jobs if not job.file.exists()]
    if missing:
        parser.error("Missing required files:\n- " + "\n- ".join(missing))
    if not args.mapping.exists():
        parser.error(f"Mapping file not found: {args.mapping}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = [execute_job(job, args.mapping) for job in jobs]

    json_path = args.output_dir / "atlas_dry_run_summary.json"
    csv_path = args.output_dir / "atlas_dry_run_summary.csv"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(results, csv_path)

    total_rows = sum(int(row.get("rows", 0) or 0) for row in results)
    total_issues = sum(int(row.get("issues", 0) or 0) for row in results)
    failures = sum(row.get("status") == "failed" for row in results)
    print(json.dumps({
        "files": len(results),
        "rows": total_rows,
        "issues": total_issues,
        "failures": failures,
        "json_report": str(json_path),
        "csv_report": str(csv_path),
    }, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
