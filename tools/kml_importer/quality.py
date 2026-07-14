from __future__ import annotations

from collections import Counter

from .models import ImportResult


def markdown_report(result: ImportResult) -> str:
    manifest = result.manifest
    issue_types = Counter(issue.split(":", 1)[0] for feature in result.features for issue in feature.quality_issues)
    geometries = Counter(feature.geometry_type for feature in result.features)
    lines = [
        "# تقرير جودة استيراد المدينة القديمة طرابلس — LSTA",
        "",
        "> تشغيل تجريبي مرحلي؛ لم تُكتب البيانات إلى PostgreSQL/PostGIS ولم تُنشر إلى Visit Libya.",
        "",
        "## المصدر",
        "",
        f"- الملف: `{manifest.source_file}`",
        f"- معرف المصدر: `{manifest.source_id}`",
        f"- SHA-256: `{manifest.source_sha256}`",
        f"- تاريخ الاستيراد: `{manifest.imported_at.isoformat()}`",
        f"- حالة التشغيل: `{manifest.status}`",
        "",
        "## الملخص",
        "",
        "| المؤشر | العدد |",
        "|---|---:|",
        f"| العناصر | {manifest.feature_count} |",
        f"| النقاط | {manifest.point_count} |",
        f"| الخطوط | {manifest.line_count} |",
        f"| المضلعات | {manifest.polygon_count} |",
        f"| الصور | {manifest.image_count} |",
        f"| بلا اسم | {manifest.unnamed_count} |",
        f"| بلا وصف | {manifest.without_description_count} |",
        f"| إحداثيات غير صالحة | {manifest.invalid_coordinate_count} |",
        "",
        "## أنواع الهندسة",
        "",
        *(f"- {name}: {count}" for name, count in sorted(geometries.items())),
        "",
        "## مشكلات الجودة",
        "",
        *(f"- {name}: {count}" for name, count in sorted(issue_types.items())),
    ]
    if not issue_types:
        lines.append("- لا توجد مشكلات مسجلة.")
    return "\n".join(lines).rstrip() + "\n"
