from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tools.import_atlas_xlsx import (
    LayerConfig,
    choose_sheet,
    clean_text,
    first_value,
    parse_float,
    sha256_file,
    validate_record,
)


def test_clean_text_normalizes_whitespace_and_nulls() -> None:
    assert clean_text("  فندق   ليبيا  ") == "فندق ليبيا"
    assert clean_text("") is None
    assert clean_text(None) is None
    assert clean_text(float("nan")) is None


def test_parse_float_accepts_comma_decimal_and_rejects_invalid() -> None:
    assert parse_float("32,875") == pytest.approx(32.875)
    assert parse_float(13.25) == pytest.approx(13.25)
    assert parse_float("غير معروف") is None
    assert parse_float(None) is None


def test_first_value_returns_first_non_empty_candidate() -> None:
    row = {"اسم الموقع": "", "اسم الفندق": "فندق الواحة", "الاسم": "بديل"}
    assert first_value(row, ["اسم الموقع", "اسم الفندق", "الاسم"]) == "فندق الواحة"


def test_validate_record_accepts_minimum_valid_record() -> None:
    record = {
        "source_record_id": "LTA-2026-HOT-00001",
        "name_ar_raw": "فندق الواحة",
        "municipality_raw": "طرابلس",
        "source_files_raw": "hotels.xlsx",
    }
    assert validate_record(record, 32.88, 13.19) == []


def test_validate_record_reports_governance_and_spatial_issues() -> None:
    record = {
        "source_record_id": None,
        "name_ar_raw": None,
        "municipality_raw": None,
        "source_files_raw": None,
    }
    issues = validate_record(record, 10.0, 40.0)
    assert {item["rule_code"] for item in issues} == {"Q001", "Q002", "Q003", "Q004", "Q005", "Q006"}
    assert sum(item["severity"] == "critical" for item in issues) == 2


def test_sha256_file_is_stable(tmp_path: Path) -> None:
    source = tmp_path / "layer.xlsx"
    source.write_bytes(b"LSTA test layer")
    assert sha256_file(source) == sha256_file(source)
    assert len(sha256_file(source)) == 64


def test_choose_sheet_prefers_explicit_sheet(tmp_path: Path) -> None:
    workbook = tmp_path / "sample.xlsx"
    with pd.ExcelWriter(workbook) as writer:
        pd.DataFrame({"الاسم": ["أ"]}).to_excel(writer, sheet_name="ملخص", index=False)
        pd.DataFrame({"الاسم": ["ب"]}).to_excel(writer, sheet_name="الفنادق", index=False)

    book = pd.ExcelFile(workbook)
    config = LayerConfig(
        key="hotels",
        code="HOTEL",
        sheet="الفنادق",
        sheet_candidates=("فنادق",),
        name_candidates=("اسم الفندق", "الاسم"),
    )
    assert choose_sheet(book, config) == "الفنادق"


def test_choose_sheet_raises_for_ambiguous_workbook(tmp_path: Path) -> None:
    workbook = tmp_path / "ambiguous.xlsx"
    with pd.ExcelWriter(workbook) as writer:
        pd.DataFrame({"الاسم": ["أ"]}).to_excel(writer, sheet_name="أ", index=False)
        pd.DataFrame({"الاسم": ["ب"]}).to_excel(writer, sheet_name="ب", index=False)

    book = pd.ExcelFile(workbook)
    config = LayerConfig(
        key="hotels",
        code="HOTEL",
        sheet=None,
        sheet_candidates=("الفنادق",),
        name_candidates=("الاسم",),
    )
    with pytest.raises(ValueError, match="Could not resolve sheet"):
        choose_sheet(book, config)
