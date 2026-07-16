from __future__ import annotations

from difflib import SequenceMatcher
from math import asin, cos, radians, sin, sqrt

from tools.merge_engine.models import SourceRecord
from tools.merge_engine.text_normalizer import compact_name, normalize_text

EARTH_RADIUS_METERS = 6_371_000


def name_similarity(first: str, second: str) -> float:
    """
    يحسب تشابه الاسمين بعد التطبيع والضغط.

    يعيد قيمة من 0 إلى 100.
    """
    normalized_first = compact_name(first)
    normalized_second = compact_name(second)

    if not normalized_first or not normalized_second:
        return 0.0

    if normalized_first == normalized_second:
        return 100.0

    return SequenceMatcher(
        None,
        normalized_first,
        normalized_second,
    ).ratio() * 100


def distance_meters(
    first: SourceRecord,
    second: SourceRecord,
) -> float | None:
    """
    يحسب المسافة بين سجلين بالمتر باستخدام معادلة Haversine.

    يعيد None إذا كانت الإحداثيات غير متوفرة.
    """
    coordinates = (
        first.latitude,
        first.longitude,
        second.latitude,
        second.longitude,
    )

    if any(value is None for value in coordinates):
        return None

    latitude_1 = radians(float(first.latitude))
    longitude_1 = radians(float(first.longitude))
    latitude_2 = radians(float(second.latitude))
    longitude_2 = radians(float(second.longitude))

    latitude_difference = latitude_2 - latitude_1
    longitude_difference = longitude_2 - longitude_1

    haversine_value = (
        sin(latitude_difference / 2) ** 2
        + cos(latitude_1)
        * cos(latitude_2)
        * sin(longitude_difference / 2) ** 2
    )

    arc = 2 * asin(sqrt(haversine_value))
    return EARTH_RADIUS_METERS * arc


def spatial_similarity(distance: float | None) -> float:
    """
    يحول المسافة بالمتر إلى درجة تشابه مكاني من 0 إلى 100.
    """
    if distance is None:
        return 0.0

    if distance <= 15:
        return 100.0

    if distance <= 30:
        return 98.0

    if distance <= 50:
        return 92.0

    if distance <= 100:
        return 82.0

    if distance <= 250:
        return 65.0

    if distance <= 500:
        return 45.0

    if distance <= 1_000:
        return 20.0

    return 0.0


def field_match(
    first: str | None,
    second: str | None,
) -> tuple[bool, bool]:
    """
    يفحص توفر الحقل في المصدرين ثم يقارن القيم بعد التطبيع.

    يعيد:
    - available: هل الحقل متوفر في المصدرين؟
    - matches: هل القيمتان متطابقتان؟
    """
    if not first or not second:
        return False, False

    normalized_first = normalize_text(first)
    normalized_second = normalize_text(second)

    if not normalized_first or not normalized_second:
        return False, False

    return True, normalized_first == normalized_second


def score_pair(
    excel_record: SourceRecord,
    kml_record: SourceRecord,
) -> tuple[float, float, float | None, bool, bool]:
    """
    يحسب درجة المطابقة النهائية بين سجل Excel وسجل KML.

    الأوزان الأساسية:
    - الاسم: 45
    - المسافة: 35
    - البلدية: 10
    - التصنيف: 10

    عند غياب البلدية أو التصنيف من أحد المصدرين،
    لا يتم احتساب الحقل كصفر، بل يعاد توزيع الدرجة
    على المكونات المتوفرة فعليًا.

    يعيد:
    - total_score
    - name_score
    - distance
    - municipality_match
    - category_match
    """
    excel_name = excel_record.name_ar or excel_record.name_en or ""
    kml_name = kml_record.name_ar or kml_record.name_en or ""

    name_score = name_similarity(
        excel_name,
        kml_name,
    )

    distance = distance_meters(
        excel_record,
        kml_record,
    )

    spatial_score = spatial_similarity(distance)

    municipality_available, municipality_match = field_match(
        excel_record.municipality,
        kml_record.municipality,
    )

    category_available, category_match = field_match(
        excel_record.category_code,
        kml_record.category_code,
    )

    score_components: list[tuple[float, float]] = [
        (name_score, 45.0),
        (spatial_score, 35.0),
    ]

    if municipality_available:
        municipality_score = 100.0 if municipality_match else 0.0
        score_components.append(
            (municipality_score, 10.0)
        )

    if category_available:
        category_score = 100.0 if category_match else 0.0
        score_components.append(
            (category_score, 10.0)
        )

    available_weight = sum(
        weight
        for _, weight in score_components
    )

    if available_weight <= 0:
        total_score = 0.0
    else:
        weighted_sum = sum(
            score * weight
            for score, weight in score_components
        )

        total_score = weighted_sum / available_weight

    # ضوابط تحفظية لمنع الثقة العالية غير المبررة.

    # لا توجد إحداثيات كافية للمقارنة.
    if distance is None:
        total_score = min(total_score, 84.0)

    # الاسم ضعيف جدًا، فلا يجوز رفع النتيجة بسبب القرب المكاني وحده.
    if name_score < 55.0:
        total_score = min(total_score, 69.0)

    # المسافة كبيرة نسبيًا، فلا يصنف السجل كتطابق قوي.
    if distance is not None and distance > 500:
        total_score = min(total_score, 79.0)

    # تعارض البلدية عند توفرها في المصدرين يخفض الثقة.
    if municipality_available and not municipality_match:
        total_score = min(total_score, 74.0)

    # تعارض التصنيف عند توفره في المصدرين يخفض الثقة.
    if category_available and not category_match:
        total_score = min(total_score, 79.0)

    total_score = max(
        0.0,
        min(total_score, 100.0),
    )

    return (
        round(total_score, 2),
        round(name_score, 2),
        None if distance is None else round(distance, 2),
        municipality_match,
        category_match,
    )