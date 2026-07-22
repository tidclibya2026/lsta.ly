from types import SimpleNamespace
from uuid import uuid4

from app.services import site_version_service
from app.services.site_version_compare_service import compare_snapshots, flatten_snapshot


def test_flatten_snapshot_supports_nested_values() -> None:
    snapshot = {
        "national_id": "LSTA-NATIONAL-000026",
        "site": {"name_ar": "نزل المدينة", "profile": {"verification_status": "draft"}},
    }
    assert flatten_snapshot(snapshot) == {
        "national_id": "LSTA-NATIONAL-000026",
        "site.name_ar": "نزل المدينة",
        "site.profile.verification_status": "draft",
    }


def test_flatten_snapshot_ignores_volatile_fields() -> None:
    snapshot = {
        "name_ar": "نزل المدينة",
        "created_at": "2026-07-20T10:00:00Z",
        "updated_at": "2026-07-21T10:00:00Z",
        "profile": {"profile_completeness_score": 80, "description": "وصف الموقع"},
    }
    assert flatten_snapshot(snapshot) == {
        "name_ar": "نزل المدينة",
        "profile.description": "وصف الموقع",
    }


def test_compare_snapshots_detects_added_removed_and_modified_fields() -> None:
    old_snapshot = {
        "state": "created",
        "name_ar": "نزل المدينة",
        "national_id": "LSTA-NATIONAL-000026",
        "description": "الوصف القديم",
    }
    new_snapshot = {
        "state": "approved",
        "name_ar": "نزل المدينة السياحي",
        "national_id": "LSTA-NATIONAL-000026",
        "municipality": "طرابلس",
    }
    result = compare_snapshots(old_snapshot, new_snapshot)
    assert result["changed"] is True
    assert result["changed_fields"] == 4
    assert result["summary"] == {"added": 1, "removed": 1, "modified": 2}
    changes = {item["field"]: item for item in result["changes"]}
    assert changes["municipality"] == {
        "field": "municipality", "change_type": "added", "old_value": None, "new_value": "طرابلس",
    }
    assert changes["description"] == {
        "field": "description", "change_type": "removed", "old_value": "الوصف القديم", "new_value": None,
    }
    assert changes["state"]["change_type"] == "modified"
    assert changes["state"]["old_value"] == "created"
    assert changes["state"]["new_value"] == "approved"
    assert changes["name_ar"]["change_type"] == "modified"


def test_compare_snapshots_detects_modified_field() -> None:
    result = compare_snapshots(
        {"name_ar": "نزل المدينة", "state": "created"},
        {"name_ar": "نزل المدينة السياحي", "state": "created"},
    )
    assert result["changed"] is True
    assert result["changed_fields"] == 1
    assert result["summary"] == {"added": 0, "removed": 0, "modified": 1}
    assert result["changes"][0] == {
        "field": "name_ar",
        "change_type": "modified",
        "old_value": "نزل المدينة",
        "new_value": "نزل المدينة السياحي",
    }


def test_compare_snapshots_returns_no_changes_for_identical_values() -> None:
    snapshot = {"state": "created", "name_ar": "نزل المدينة", "national_id": "LSTA-NATIONAL-000026"}
    assert compare_snapshots(snapshot, snapshot) == {
        "changed": False,
        "changed_fields": 0,
        "summary": {"added": 0, "removed": 0, "modified": 0},
        "changes": [],
    }


def test_compare_snapshots_handles_nested_changes() -> None:
    old_snapshot = {
        "profile": {"short_description_ar": "الوصف القديم", "verification_status": "draft"}
    }
    new_snapshot = {
        "profile": {"short_description_ar": "الوصف الجديد", "verification_status": "approved"}
    }
    result = compare_snapshots(old_snapshot, new_snapshot)
    assert result["changed_fields"] == 2
    assert {item["field"] for item in result["changes"]} == {
        "profile.short_description_ar", "profile.verification_status",
    }


def test_compare_versions_preserves_legacy_top_level_contract(monkeypatch) -> None:
    versions = {
        1: SimpleNamespace(snapshot={"name_ar": "لبدة", "status": "draft"}),
        2: SimpleNamespace(snapshot={"name_ar": "لبدة الكبرى", "status": "draft"}),
    }
    monkeypatch.setattr(site_version_service, "get_version", lambda _session, _site_id, number: versions[number])

    result = site_version_service.compare_versions(object(), uuid4(), 1, 2)

    assert result == {"name_ar": {"before": "لبدة", "after": "لبدة الكبرى"}}
