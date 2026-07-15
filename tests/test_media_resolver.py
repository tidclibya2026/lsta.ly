import csv
import json
from pathlib import Path

from tools.media_resolver.cli import audit, download_approved
from tools.media_resolver.image_metadata import inspect_image
from tools.media_resolver.url_validator import classify_url


def test_classifies_https_google_broken_and_local_links() -> None:
    assert classify_url("https://example.org/site.jpg").status == "valid_https"
    assert classify_url("https://lh3.googleusercontent.com/expired").status == "googleusercontent"
    assert classify_url("https://maps.google.com/image").status == "google_maps"
    assert classify_url("media/site.jpg").status == "relative_path"
    assert classify_url("\n").status == "malformed"


def test_validates_image_signature_and_mime() -> None:
    metadata = inspect_image(b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png")
    assert metadata.mime_type == "image/png"


def test_audit_supports_multiple_images_and_writes_utf8_csv(tmp_path: Path) -> None:
    source = tmp_path / "features.json"
    source.write_text(
        json.dumps(
            {
                "features": [
                    {
                        "feature_id": "F-1",
                        "name_ar": "موقع",
                        "image_urls": ["https://example.org/a.jpg", "https://lh3.googleusercontent.com/x"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report, review, counts = audit(source, tmp_path / "reports")
    assert report.exists() and review.read_bytes().startswith(b"\xef\xbb\xbf")
    assert counts["valid_https"] == 1 and counts["googleusercontent"] == 1


def test_download_requires_both_content_and_rights_approval(tmp_path: Path) -> None:
    review = tmp_path / "review.csv"
    with review.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["feature_id", "original_url", "normalized_url", "review_status", "rights_status"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "feature_id": "F-1",
                "original_url": "https://example.org/a.jpg",
                "normalized_url": "https://example.org/a.jpg",
                "review_status": "pending_review",
                "rights_status": "unknown",
            }
        )
    manifest = download_approved(review, tmp_path / "media", None)
    assert json.loads(manifest.read_text(encoding="utf-8"))["asset_count"] == 0
