from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .image_metadata import ImageMetadata, inspect_image

MAX_IMAGE_BYTES = 15 * 1024 * 1024


@dataclass(frozen=True)
class DownloadedImage:
    data: bytes
    metadata: ImageMetadata


def download_image(url: str, *, timeout: float = 15, max_bytes: int = MAX_IMAGE_BYTES) -> DownloadedImage:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("approved downloads require a valid HTTPS URL")
    try:
        address = ip_address(parsed.hostname)
        if not address.is_global:
            raise ValueError("private or local network targets are not allowed")
    except ValueError as exc:
        if "not allowed" in str(exc):
            raise
    request = Request(url, headers={"User-Agent": "LSTA-Media-Resolver/1.0", "Accept": "image/*"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - only called after explicit approval
        declared = int(response.headers.get("Content-Length") or 0)
        if declared > max_bytes:
            raise ValueError("image exceeds maximum allowed size")
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("image exceeds maximum allowed size")
        metadata = inspect_image(data, response.headers.get("Content-Type", ""))
        return DownloadedImage(data, metadata)
