from pathlib import Path

from tools.assign_municipalities import export_review


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params):
        assert "gis.v_municipality_assignment_review" in query
        assert params
        return FakeCursor(self.rows)


def test_export_review_writes_expected_columns(tmp_path: Path) -> None:
    output = tmp_path / "municipality_review.csv"
    rows = [
        (
            "LTA-2026-OLD-00001",
            "مدينة غدامس القديمة",
            "30.133",
            "9.500",
            "غدامس",
            "contains",
            0,
            100,
            "pending",
            None,
        )
    ]
    count = export_review(FakeConnection(rows), "run-id", output)  # type: ignore[arg-type]
    text = output.read_text(encoding="utf-8-sig")
    assert count == 1
    assert "proposed_municipality" in text
    assert "مدينة غدامس القديمة" in text
    assert "contains" in text
