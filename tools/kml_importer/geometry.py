from __future__ import annotations

from typing import Any

from lxml import etree
from shapely.geometry import LineString, Point, Polygon, mapping
from shapely.geometry.base import BaseGeometry

NS = {"k": "http://www.opengis.net/kml/2.2"}


def parse_geometry(node: etree._Element | None) -> tuple[dict[str, Any] | None, list[str]]:
    issues: list[str] = []
    if node is None:
        return None, ["missing_geometry"]
    local = etree.QName(node).localname
    try:
        if local == "Point":
            coords = _coordinates(node.findtext("k:coordinates", namespaces=NS) or "", issues)
            geometry: BaseGeometry = Point(coords[0])
        elif local == "LineString":
            geometry = LineString(_coordinates(node.findtext("k:coordinates", namespaces=NS) or "", issues))
        elif local == "Polygon":
            rings = [_coordinates(value, issues) for value in node.xpath(".//k:LinearRing/k:coordinates/text()", namespaces=NS)]
            geometry = Polygon(rings[0], rings[1:])
        elif local == "MultiGeometry":
            children = [parse_geometry(child) for child in node if etree.QName(child).localname in {"Point", "LineString", "Polygon", "MultiGeometry"}]
            issues.extend(issue for _, child_issues in children for issue in child_issues)
            geometries = [item for item, _ in children if item]
            return {"type": "GeometryCollection", "geometries": geometries}, issues
        else:
            return None, [f"unsupported_geometry:{local}"]
    except (ValueError, IndexError) as exc:
        issues.append(f"invalid_geometry:{exc}")
        return None, issues
    if not geometry.is_valid:
        issues.append("invalid_geometry:shapely_validation")
    return mapping(geometry), issues


def coordinates_from_geometry(geometry: dict[str, Any] | None) -> Any:
    if not geometry:
        return None
    return geometry.get("coordinates", geometry.get("geometries"))


def _coordinates(raw: str, issues: list[str]) -> list[tuple[float, ...]]:
    result: list[tuple[float, ...]] = []
    for token in raw.replace("\n", " ").split():
        try:
            values = tuple(float(item) for item in token.split(",") if item != "")
            if len(values) < 2 or not (-180 <= values[0] <= 180 and -90 <= values[1] <= 90):
                raise ValueError(f"coordinate_out_of_range:{token}")
            result.append(values[:3])
        except ValueError:
            issues.append(f"invalid_coordinate:{token}")
    if not result:
        raise ValueError("no_valid_coordinates")
    return result
