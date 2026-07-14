from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.kml_importer.description_parser import parse_description
from tools.kml_importer.main import run_import
from tools.kml_importer.parser import parse_kml

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Style id="s"><IconStyle><color>ff112233</color><Icon><href>https://example.org/a.jpg</href></Icon></IconStyle></Style>
<StyleMap id="sm"><Pair><key>normal</key><styleUrl>#s</styleUrl></Pair></StyleMap>
<Folder><name>المدينة القديمة</name>
<Placemark><name>معلم</name><styleUrl>#sm</styleUrl><description><![CDATA[<p>وصف المعلم</p><table><tr><td>النوع</td><td>تراث</td></tr></table><a href="https://example.org">رابط</a><img src="https://example.org/a.jpg"><custom>x</custom>]]></description><ExtendedData><Data name="status"><value>sample</value></Data></ExtendedData><Point><coordinates>13.18,32.89,0</coordinates></Point></Placemark>
<Placemark><LineString><coordinates>13,32 14,33</coordinates></LineString></Placemark>
<Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>10,30 11,30 11,31 10,30</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
<Placemark><MultiGeometry><Point><coordinates>12,31</coordinates></Point><LineString><coordinates>12,31 13,31</coordinates></LineString></MultiGeometry></Placemark>
</Folder></Document></kml>"""


def test_description_keeps_html_and_extracts_content() -> None:
    html = '<table><tr><td>مفتاح</td><td>قيمة</td></tr></table><a href="https://lsta.ly">LSTA</a><x-tag>غير معروف</x-tag>'
    parsed = parse_description(html)
    assert parsed.html == html
    assert parsed.tables == {"مفتاح": "قيمة"}
    assert parsed.external_links == ["https://lsta.ly"]
    assert parsed.unknown_fragments == ["<x-tag>غير معروف</x-tag>"]


def test_parser_supports_required_geometries_and_ids(tmp_path: Path) -> None:
    source = tmp_path / "sample.kml"
    source.write_text(KML, encoding="utf-8")
    features = parse_kml(source, "SRC-2026-00001")
    assert [feature.geometry_type for feature in features] == ["Point", "LineString", "Polygon", "GeometryCollection"]
    assert features[0].feature_id == "LSTA-OLD-TRIPOLI-000001"
    assert features[0].folder_name == "المدينة القديمة"
    assert features[0].extended_data == {"status": "sample"}
    assert features[0].description_tables == {"النوع": "تراث"}
    assert features[0].source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert features[0].icon_url == "https://example.org/a.jpg"


def test_run_import_writes_all_outputs(tmp_path: Path) -> None:
    source = tmp_path / "sample.kml"
    source.write_text(KML, encoding="utf-8")
    output = tmp_path / "processed"
    report = tmp_path / "reports" / "quality.md"
    result, paths = run_import(source, output, report)
    assert len(paths) == 7
    assert all(path.exists() for path in paths)
    assert result.manifest.point_count == 2
    assert result.manifest.line_count == 2
    assert result.manifest.polygon_count == 1
    manifest = json.loads((output / "old_tripoli_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_id"] == "SRC-2026-00001"
    assert manifest["status"] == "success_with_issues"
    assert manifest["named_features"] == 1
    assert manifest["unnamed_lines"] == 1
    review_csv = tmp_path / "reports" / "old_tripoli_missing_names_review.csv"
    assert review_csv.read_bytes().startswith(b"\xef\xbb\xbf")
