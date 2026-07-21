from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.models import SiteVersion
from app.services.site_version_service import get_version

DEFAULT_IGNORED_FIELDS = frozenset(
    {
        "created_at",
        "updated_at",
        "calculated_at",
        "profile_completeness_score",
    }
)


def _join_path(parent: str, child: str) -> str:
    """Build a stable dotted path for nested snapshot fields."""
    return f"{parent}.{child}" if parent else child


def flatten_snapshot(
    value: Any,
    *,
    parent_path: str = "",
    ignored_fields: set[str] | frozenset[str] = DEFAULT_IGNORED_FIELDS,
) -> dict[str, Any]:
    """
    Convert a nested JSON-compatible snapshot into dotted field paths.

    Example:
        {
            "site": {
                "name_ar": "لبدة",
                "profile": {"status": "approved"},
            }
        }

    becomes:
        {
            "site.name_ar": "لبدة",
            "site.profile.status": "approved",
        }

    Lists are retained as complete values because their ordering may be
    semantically meaningful.
    """
    flattened: dict[str, Any] = {}

    if isinstance(value, Mapping):
        if not value and parent_path:
            flattened[parent_path] = {}

        for raw_key, child_value in value.items():
            key = str(raw_key)

            if key in ignored_fields:
                continue

            path = _join_path(parent_path, key)

            if isinstance(child_value, Mapping):
                flattened.update(
                    flatten_snapshot(
                        child_value,
                        parent_path=path,
                        ignored_fields=ignored_fields,
                    )
                )
            else:
                flattened[path] = child_value

        return flattened

    if parent_path:
        flattened[parent_path] = value

    return flattened


def compare_snapshots(
    from_snapshot: Mapping[str, Any],
    to_snapshot: Mapping[str, Any],
    *,
    ignored_fields: set[str] | frozenset[str] = DEFAULT_IGNORED_FIELDS,
) -> dict[str, Any]:
    """
    Compare two registry snapshots.

    Change types:
    - added: field exists only in the target snapshot.
    - removed: field exists only in the source snapshot.
    - modified: field exists in both snapshots but has a different value.
    """
    old_values = flatten_snapshot(
        from_snapshot,
        ignored_fields=ignored_fields,
    )
    new_values = flatten_snapshot(
        to_snapshot,
        ignored_fields=ignored_fields,
    )

    changes: list[dict[str, Any]] = []

    for field in sorted(set(old_values) | set(new_values)):
        exists_before = field in old_values
        exists_after = field in new_values

        old_value = old_values.get(field)
        new_value = new_values.get(field)

        if exists_before and not exists_after:
            change_type = "removed"
        elif not exists_before and exists_after:
            change_type = "added"
        elif old_value != new_value:
            change_type = "modified"
        else:
            continue

        changes.append(
            {
                "field": field,
                "change_type": change_type,
                "old_value": old_value if exists_before else None,
                "new_value": new_value if exists_after else None,
            }
        )

    added_count = sum(item["change_type"] == "added" for item in changes)
    removed_count = sum(item["change_type"] == "removed" for item in changes)
    modified_count = sum(item["change_type"] == "modified" for item in changes)

    return {
        "changed": bool(changes),
        "changed_fields": len(changes),
        "summary": {
            "added": added_count,
            "removed": removed_count,
            "modified": modified_count,
        },
        "changes": changes,
    }


def compare_site_versions(
    session: Session,
    site_id: Any,
    from_version_number: int,
    to_version_number: int,
) -> dict[str, Any]:
    """
    Load and compare two persisted versions belonging to the same site.
    """
    if from_version_number == to_version_number:
        version = get_version(session, site_id, from_version_number)

        return {
            "site_id": str(site_id),
            "from_version": version.version_number,
            "to_version": version.version_number,
            "from_created_at": version.created_at,
            "to_created_at": version.created_at,
            "from_change_summary": version.change_summary,
            "to_change_summary": version.change_summary,
            "changed": False,
            "changed_fields": 0,
            "summary": {
                "added": 0,
                "removed": 0,
                "modified": 0,
            },
            "changes": [],
        }

    from_version: SiteVersion = get_version(
        session,
        site_id,
        from_version_number,
    )
    to_version: SiteVersion = get_version(
        session,
        site_id,
        to_version_number,
    )

    comparison = compare_snapshots(
        from_version.snapshot,
        to_version.snapshot,
    )

    return {
        "site_id": str(site_id),
        "from_version": from_version.version_number,
        "to_version": to_version.version_number,
        "from_created_at": from_version.created_at,
        "to_created_at": to_version.created_at,
        "from_change_summary": from_version.change_summary,
        "to_change_summary": to_version.change_summary,
        **comparison,
    }