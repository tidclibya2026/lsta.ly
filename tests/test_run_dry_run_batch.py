from __future__ import annotations

import csv
from pathlib import Path

from tools.run_dry_run_batch import LayerJob, write_csv


def test_layer_job_preserves_layer_and_file(tmp_path: Path) -> None:
    file = tmp_path / "hotels.xlsx"
    job = LayerJob("hotels", file)
    assert job.layer == "hotels"
    assert job.file == file


def test_write_csv_emits_government_review_columns(tmp_path: Path) -> None:
    output = tmp_path / "summary.csv"
    write_csv(
        [
            {
                "layer": "hotels",
                "file": "hotels.xlsx",
                "sheet": "الفنادق",
                "rows": 10,
                "issues": 2,
                "sha256": "abc",
                "dry_run": True,
                "status": "completed",
            }
        ],
        output,
    )

    with output.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["layer"] == "hotels"
    assert rows[0]["rows"] == "10"
    assert rows[0]["status"] == "completed"
