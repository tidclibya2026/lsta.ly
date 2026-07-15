from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from .deduplicator import existing_checksums, sha256_bytes
from .downloader import download_image
from .manifest import write_manifest
from .url_validator import MediaUrlAssessment, classify_url

REVIEW_COLUMNS = [
    "feature_id",
    "site_name",
    "original_url",
    "normalized_url",
    "domain",
    "status",
    "resolution_method",
    "local_path",
    "error",
    "review_status",
    "rights_status",
]


def load_features(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload if isinstance(payload, list) else payload.get("features") or payload.get("items") or []
    if not isinstance(items, list):
        raise ValueError("input must contain a list of features")
    return [item.get("properties", item) for item in items if isinstance(item, dict)]


def audit(input_path: Path, output: Path) -> tuple[Path, Path, Counter[str]]:
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    feature_count = 0
    for feature in load_features(input_path):
        urls = feature.get("image_urls") or []
        if isinstance(urls, str):
            urls = [urls]
        if urls:
            feature_count += 1
        for url in urls:
            result: MediaUrlAssessment = classify_url(url)
            rows.append(
                {
                    "feature_id": str(feature.get("feature_id") or ""),
                    "site_name": str(feature.get("name_ar") or ""),
                    "original_url": result.original_url,
                    "normalized_url": result.normalized_url,
                    "domain": result.domain,
                    "status": result.status,
                    "resolution_method": result.resolution_method,
                    "local_path": result.local_path,
                    "error": result.error,
                    "review_status": "pending_review",
                    "rights_status": "unknown",
                }
            )
    csv_path = output / "old_tripoli_image_review.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(row["status"] for row in rows)
    unavailable = sum(value for key, value in counts.items() if key != "valid_https")
    report_path = output / "old_tripoli_image_audit.md"
    lines = [
        "# تدقيق صور المدينة القديمة طرابلس — LSTA",
        "",
        "هذه عملية تدقيق بنيوي لا تقوم بتنزيل الصور أو اعتماد حقوق استخدامها.",
        "",
        "## ملخص مجموعة البيانات",
        "",
        f"- العناصر: {len(load_features(input_path))}",
        f"- العناصر التي تحمل صورًا: {feature_count}",
        f"- إجمالي مراجع الصور: {len(rows)}",
        f"- الصور المتاحة مبدئيًا عبر HTTPS غير تابع لـGoogle: {counts['valid_https']}",
        f"- الصور غير المتاحة للإنتاج المباشر أو التي تحتاج معالجة: {unavailable}",
        "",
        "## التصنيف",
        "",
        "| الحالة | العدد | النسبة |",
        "|---|---:|---:|",
    ]
    for status in sorted(
        set(counts)
        | {
            "valid_https",
            "http_only",
            "googleusercontent",
            "google_maps",
            "relative_path",
            "embedded_kmz",
            "malformed",
            "unavailable",
        }
    ):
        count = counts[status]
        lines.append(f"| `{status}` | {count} | {(count / len(rows) * 100 if rows else 0):.1f}% |")
    lines += [
        "",
        "## تقييم المخاطر",
        "",
        "- روابط Google وGoogleusercontent مؤقتة أو مرتبطة بسياسات منصة خارجية؛ لا تُعامل كأصول إنتاج دائمة.",
        "- لا تعني صلاحية HTTPS أن حقوق النشر معتمدة. يجب ضبط `rights_status=approved_public` و`review_status=approved` قبل التنزيل والنشر العام.",
        "- الروابط غير المعتمدة تستخدم placeholder حكوميًا بدل رمز الصورة المكسورة.",
        "",
        "## الإجراء المقترح",
        "",
        "راجع CSV، وثّق الحقوق، ثم شغّل `download-approved` للصفوف المعتمدة فقط.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path, csv_path, counts


def download_approved(review_file: Path, output: Path, public_output: Path | None = None) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    checksums = existing_checksums(output)
    manifest_items: list[dict[str, Any]] = []
    with review_file.open(encoding="utf-8-sig", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream), start=1):
            if row.get("review_status") != "approved" or row.get("rights_status") != "approved_public":
                continue
            try:
                image = download_image(row.get("normalized_url") or row["original_url"])
                digest = sha256_bytes(image.data)
                if digest in checksums:
                    path = checksums[digest]
                    duplicate = True
                else:
                    safe_id = "".join(char if char.isalnum() or char in "-_" else "-" for char in row["feature_id"])
                    path = output / f"{safe_id}-{index:03d}{image.metadata.extension}"
                    path.write_bytes(image.data)
                    checksums[digest] = path
                    duplicate = False
                if public_output:
                    public_output.mkdir(parents=True, exist_ok=True)
                    public_path = public_output / path.name
                    if not public_path.exists():
                        shutil.copy2(path, public_path)
                manifest_items.append(
                    {
                        "feature_id": row["feature_id"],
                        "original_url": row["original_url"],
                        "local_path": path.as_posix(),
                        "sha256": digest,
                        "mime_type": image.metadata.mime_type,
                        "size_bytes": image.metadata.size_bytes,
                        "rights_status": "approved_public",
                        "duplicate": duplicate,
                    }
                )
            except Exception as exc:  # keep the approved batch auditable
                manifest_items.append(
                    {
                        "feature_id": row.get("feature_id"),
                        "original_url": row.get("original_url"),
                        "error": str(exc),
                        "rights_status": row.get("rights_status"),
                    }
                )
    return write_manifest(output, manifest_items)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m tools.media_resolver")
    commands = root.add_subparsers(dest="command", required=True)
    audit_cmd = commands.add_parser("audit")
    audit_cmd.add_argument("--input", required=True, type=Path)
    audit_cmd.add_argument("--output", required=True, type=Path)
    download = commands.add_parser("download-approved")
    download.add_argument("--review-file", required=True, type=Path)
    download.add_argument("--output", required=True, type=Path)
    download.add_argument("--public-output", type=Path, default=Path("apps/atlas-government/public/media/old-tripoli"))
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "audit":
        report, review, counts = audit(args.input, args.output)
        print(
            json.dumps(
                {"report": str(report), "review": str(review), "counts": counts}, ensure_ascii=False, default=dict
            )
        )
        return 0
    manifest = download_approved(args.review_file, args.output, args.public_output)
    print(manifest)
    return 0
