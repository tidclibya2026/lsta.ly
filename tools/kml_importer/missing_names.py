from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from .models import AtlasFeature

REVIEW_FIELDS = [
    "feature_id",
    "geometry_type",
    "folder_name",
    "description_text",
    "image_count",
    "extended_data",
    "review_category",
    "proposed_name",
    "proposed_name_confidence",
    "review_status",
    "reviewer_notes",
]

FCLASS_AR = {
    "residential": "مسار سكني",
    "trunk": "طريق رئيسي",
    "primary": "طريق أولي",
    "secondary": "طريق ثانوي",
    "tertiary": "طريق فرعي",
    "service": "مسار خدمة",
    "unclassified": "مسار غير مصنف",
    "footway": "ممر مشاة",
    "path": "مسار",
}


def write_missing_names_analysis(features: list[AtlasFeature], report_dir: Path, basename: str) -> list[Path]:
    missing = [feature for feature in features if "missing_name" in feature.quality_issues]
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{basename}_missing_names_analysis.md"
    csv_path = report_dir / f"{basename}_missing_names_review.csv"
    report_path.write_text(_markdown(missing), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(_review_row(feature) for feature in missing)
    return [report_path, csv_path]


def _review_row(feature: AtlasFeature) -> dict[str, object]:
    category = _category(feature)
    proposed_name, confidence = _proposal(feature, category)
    return {
        "feature_id": feature.feature_id,
        "geometry_type": feature.geometry_type,
        "folder_name": feature.folder_name,
        "description_text": feature.description_text,
        "image_count": len(feature.image_urls),
        "extended_data": json.dumps(feature.extended_data, ensure_ascii=False, separators=(",", ":")),
        "review_category": category,
        "proposed_name": proposed_name,
        "proposed_name_confidence": confidence,
        "review_status": "pending_review",
        "reviewer_notes": "",
    }


def _category(feature: AtlasFeature) -> str:
    if feature.geometry_type == "Point" and (feature.image_urls or feature.description_text):
        return "موقع سياحي مستقل"
    if feature.geometry_type == "LineString":
        return "مسار"
    if feature.geometry_type == "Polygon":
        return "حد"
    if feature.geometry_type == "GeometryCollection":
        return "جزء هندسي"
    return "عنصر يحتاج مراجعة"


def _proposal(feature: AtlasFeature, category: str) -> tuple[str, str]:
    fclass = feature.extended_data.get("fclass", "").strip().lower()
    osm_id = feature.extended_data.get("osm_id", "").strip()
    if category == "مسار" and fclass in FCLASS_AR:
        suffix = f" (مرجع OSM {osm_id})" if osm_id else ""
        return f"{FCLASS_AR[fclass]}{suffix}", "low"
    if feature.folder_name:
        return f"عنصر ضمن {feature.folder_name}", "low"
    return "", "none"


def _markdown(features: list[AtlasFeature]) -> str:
    geometry = Counter(feature.geometry_type for feature in features)
    folders = Counter(feature.folder_name or "(بلا مجلد)" for feature in features)
    categories = Counter(_category(feature) for feature in features)
    lines = [
        "# تحليل العناصر بلا اسم — المدينة القديمة طرابلس",
        "",
        "> لا يتضمن هذا التقرير أسماء نهائية. جميع المقترحات قرائن منخفضة الثقة وتحتاج اعتماد مراجع بشري.",
        "",
        "## الملخص",
        "",
        f"- إجمالي العناصر بلا اسم: {len(features)}",
        f"- لها وصف: {sum(bool(feature.description_text) for feature in features)}",
        f"- لها صورة: {sum(bool(feature.image_urls) for feature in features)}",
        f"- لها ExtendedData: {sum(bool(feature.extended_data) for feature in features)}",
        "",
        "## حسب نوع الهندسة",
        "",
        *(f"- {name}: {count}" for name, count in sorted(geometry.items())),
        "",
        "## حسب المجلد المصدر",
        "",
        *(f"- {name}: {count}" for name, count in sorted(folders.items())),
        "",
        "## التصنيف المقترح للمراجعة",
        "",
        *(f"- {name}: {count}" for name, count in sorted(categories.items())),
        "",
        "## منهجية الاقتراح",
        "",
        "- تصنّف الخطوط كمسارات والمضلعات كحدود والهندسات المركبة كأجزاء هندسية.",
        "- يُستفاد من `fclass` و`osm_id` لتقديم قرينة مراجعة فقط.",
        "- تبقى حالة كل سجل `pending_review` ولا يُعتمد أي اسم آليًا.",
    ]
    return "\n".join(lines).rstrip() + "\n"
