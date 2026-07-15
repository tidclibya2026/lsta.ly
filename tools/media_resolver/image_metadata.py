from __future__ import annotations

from dataclasses import dataclass

MIME_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"GIF87a", "image/gif", ".gif"),
    (b"GIF89a", "image/gif", ".gif"),
    (b"RIFF", "image/webp", ".webp"),
)


@dataclass(frozen=True)
class ImageMetadata:
    mime_type: str
    extension: str
    size_bytes: int


def inspect_image(data: bytes, content_type: str = "") -> ImageMetadata:
    for signature, mime, extension in MIME_SIGNATURES:
        if data.startswith(signature) and (mime != "image/webp" or data[8:12] == b"WEBP"):
            if content_type and content_type.split(";", 1)[0].lower() not in {mime, "application/octet-stream"}:
                raise ValueError("MIME header does not match image content")
            return ImageMetadata(mime, extension, len(data))
    raise ValueError("unsupported or invalid image content")
