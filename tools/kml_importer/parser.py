from __future__ import annotations

import hashlib
from pathlib import Path

from lxml import etree

from .description_parser import parse_description
from .geometry import coordinates_from_geometry, parse_geometry
from .models import AtlasFeature

NS = {"k": "http://www.opengis.net/kml/2.2"}
GEOMETRY_NAMES = {"Point", "LineString", "Polygon", "MultiGeometry"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_kml(path: Path, source_id: str, feature_prefix: str = "LSTA-OLD-TRIPOLI") -> list[AtlasFeature]:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=True, huge_tree=True)
    root = etree.parse(str(path), parser).getroot()
    checksum = sha256_file(path)
    styles, style_maps = _styles(root)
    features: list[AtlasFeature] = []
    for index, placemark in enumerate(root.xpath(".//k:Placemark", namespaces=NS), start=1):
        folder = _folder_name(placemark)
        raw_description = placemark.findtext("k:description", namespaces=NS) or ""
        description = parse_description(raw_description)
        geometry_node = next((child for child in placemark if etree.QName(child).localname in GEOMETRY_NAMES), None)
        geometry, issues = parse_geometry(geometry_node)
        style_url = (placemark.findtext("k:styleUrl", namespaces=NS) or "").lstrip("#")
        style_key = style_maps.get(style_url, style_url)
        icon, color = styles.get(style_key, ("", ""))
        inline = placemark.find("k:Style", namespaces=NS)
        if inline is not None:
            icon, color = _style_values(inline)
        name = (placemark.findtext("k:name", namespaces=NS) or "").strip()
        if not name:
            issues.append("missing_name")
        if not raw_description.strip():
            issues.append("missing_description")
        image_urls = list(dict.fromkeys([*description.image_urls, *([icon] if icon else [])]))
        features.append(
            AtlasFeature(
                source_id=source_id,
                feature_id=f"{feature_prefix}-{index:06d}",
                name_ar=name,
                name_en="",
                description_html=raw_description,
                description_text=description.text,
                description_tables=description.tables,
                description_links=description.external_links,
                description_unknown=description.unknown_fragments,
                geometry_type=geometry["type"] if geometry else "Unknown",
                coordinates=coordinates_from_geometry(geometry),
                geometry=geometry,
                folder_name=folder,
                extended_data=_extended_data(placemark),
                image_urls=image_urls,
                source_file=path.name,
                source_sha256=checksum,
                quality_issues=issues,
                style_url=style_url,
                icon_url=icon,
                color=color,
            )
        )
    return features


def _folder_name(placemark: etree._Element) -> str:
    folders = placemark.xpath("ancestor::k:Folder/k:name/text()", namespaces=NS)
    return " / ".join(value.strip() for value in folders if value.strip())


def _extended_data(placemark: etree._Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in placemark.xpath(".//k:ExtendedData//k:Data", namespaces=NS):
        result[node.get("name", "")] = "".join(node.xpath("./k:value//text()", namespaces=NS)).strip()
    for node in placemark.xpath(".//k:ExtendedData//k:SimpleData", namespaces=NS):
        result[node.get("name", "")] = "".join(node.itertext()).strip()
    return result


def _styles(root: etree._Element) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    styles = {node.get("id", ""): _style_values(node) for node in root.xpath(".//k:Style[@id]", namespaces=NS)}
    maps: dict[str, str] = {}
    for node in root.xpath(".//k:StyleMap[@id]", namespaces=NS):
        normal = node.xpath("./k:Pair[k:key='normal']/k:styleUrl/text()", namespaces=NS)
        if normal:
            maps[node.get("id", "")] = normal[0].lstrip("#")
    return styles, maps


def _style_values(node: etree._Element) -> tuple[str, str]:
    icon = node.xpath("string(.//k:Icon/k:href)", namespaces=NS).strip()
    colors = node.xpath(".//k:IconStyle/k:color/text() | .//k:LineStyle/k:color/text() | .//k:PolyStyle/k:color/text()", namespaces=NS)
    return icon, colors[0].strip() if colors else ""
