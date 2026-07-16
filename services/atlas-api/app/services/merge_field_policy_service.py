"""Deterministic, layer-neutral field policy for controlled merges."""
from typing import Any

KML_FIELDS = {"geometry", "latitude", "longitude", "images", "media", "spatial_description", "folder_name"}
EXCEL_FIELDS = {"name_ar", "name_en", "municipality", "classification", "contact_information", "license_data", "operational_attributes", "statistical_attributes"}
SKIPPED_FIELDS = {"description_html", "extended_data", "raw_html", "unknown_fields"}


def build_field_merge_plan(current: dict[str, Any], proposed: dict[str, Any], field_sources: dict[str, Any]) -> list[dict[str, Any]]:
    plan = []
    for field in sorted(set(proposed) | set(current)):
        source = "kml" if field in KML_FIELDS else "excel" if field in EXCEL_FIELDS else field_sources.get(field, "configured")
        old, new = current.get(field), proposed.get(field)
        if field in SKIPPED_FIELDS:
            action, reason = "skip", "raw or unconfigured source field"
        elif new in (None, "", [], {}):
            action, reason = "keep", "empty input never overwrites registry data"
        elif old == new:
            action, reason = "keep", "unchanged"
        else:
            action, reason = "update", f"authoritative {source} value"
        plan.append({"field": field, "current_value": old, "proposed_value": new, "source": source, "action": action, "reason": reason, "requires_confirmation": field == "geometry" and action == "update"})
    return plan


def apply_plan(current: dict[str, Any], plan: list[dict[str, Any]]) -> dict[str, Any]:
    result = dict(current)
    for item in plan:
        if item["action"] == "update" and not item.get("requires_confirmation"):
            result[item["field"]] = item["proposed_value"]
    return result
