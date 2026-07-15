from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse

STATUSES = {
    "valid_https",
    "http_only",
    "googleusercontent",
    "google_maps",
    "relative_path",
    "embedded_kmz",
    "malformed",
    "unavailable",
}
GOOGLE_USER_DOMAINS = {"googleusercontent.com", "mymaps.usercontent.google.com"}


@dataclass(frozen=True)
class MediaUrlAssessment:
    original_url: str
    normalized_url: str
    domain: str
    status: str
    resolution_method: str
    local_path: str = ""
    error: str = ""


def _domain(hostname: str | None) -> str:
    return (hostname or "").lower().removeprefix("www.")


def classify_url(value: object) -> MediaUrlAssessment:
    original = str(value or "").strip()
    if not original or any(char in original for char in "\r\n\x00"):
        return MediaUrlAssessment(original, "", "", "malformed", "rejected", error="empty or unsafe URL")
    if original.lower().startswith(("kmz://", "embedded://")) or re.search(
        r"(?:^|[/\\])files[/\\].+\.(?:jpe?g|png|gif|webp)$", original, re.I
    ):
        return MediaUrlAssessment(
            original, original.replace("\\", "/"), "", "embedded_kmz", "embedded_asset", local_path=original
        )
    parsed = urlparse(original)
    if parsed.scheme not in {"http", "https"}:
        if parsed.scheme or original.startswith("//"):
            return MediaUrlAssessment(original, "", "", "malformed", "rejected", error="unsupported URL scheme")
        normalized = Path(original).as_posix()
        return MediaUrlAssessment(original, normalized, "", "relative_path", "local_lookup", local_path=normalized)
    domain = _domain(parsed.hostname)
    if not domain or " " in domain:
        return MediaUrlAssessment(original, "", domain, "malformed", "rejected", error="invalid hostname")
    normalized = urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", parsed.query, ""))
    if domain == "googleusercontent.com" or domain.endswith(".googleusercontent.com") or domain in GOOGLE_USER_DOMAINS:
        return MediaUrlAssessment(
            original,
            normalized,
            domain,
            "googleusercontent",
            "rights_and_availability_review",
            error="ephemeral Google-hosted URL",
        )
    if domain.endswith("google.com") or domain.endswith("gstatic.com") or "googleapis.com" in domain:
        return MediaUrlAssessment(
            original,
            normalized,
            domain,
            "google_maps",
            "replace_with_reviewed_local_asset",
            error="Google Maps asset is not a durable production source",
        )
    if parsed.scheme == "http":
        return MediaUrlAssessment(
            original, normalized, domain, "http_only", "https_upgrade_review", error="insecure HTTP URL"
        )
    return MediaUrlAssessment(original, normalized, domain, "valid_https", "remote_reference_review")
