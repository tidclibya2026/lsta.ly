from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup


@dataclass(slots=True)
class ParsedDescription:
    html: str
    text: str
    tables: dict[str, str] = field(default_factory=dict)
    image_urls: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    unknown_fragments: list[str] = field(default_factory=list)


def parse_description(html: str) -> ParsedDescription:
    soup = BeautifulSoup(html or "", "lxml")
    tables: dict[str, str] = {}
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("th,td")]
        if len(cells) >= 2 and cells[0]:
            tables[cells[0]] = " | ".join(cells[1:])
    images = _unique(tag.get("src", "").strip() for tag in soup.select("img[src]"))
    links = _unique(tag.get("href", "").strip() for tag in soup.select("a[href]") if _is_external(tag.get("href", "")))
    known = {"html", "body", "p", "br", "div", "span", "b", "strong", "i", "em", "ul", "ol", "li", "table", "thead", "tbody", "tr", "td", "th", "a", "img", "h1", "h2", "h3", "h4", "h5", "h6"}
    unknown = [str(tag) for tag in soup.find_all(True) if tag.name not in known]
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    return ParsedDescription(html=html or "", text=text, tables=tables, image_urls=images, external_links=links, unknown_fragments=unknown)


def _is_external(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _unique(values: object) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))
