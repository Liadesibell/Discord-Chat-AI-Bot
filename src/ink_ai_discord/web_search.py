from __future__ import annotations

import ipaddress
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx

SEARCH_RESULT_LIMIT = 5
SEARCH_TIMEOUT_SECONDS = 12
SEARCH_PATTERNS = (
    re.compile(r"\bweb\s+tarama(?:sı)?\s+yap\b", re.IGNORECASE),
    re.compile(r"\bweb\s+araştırma(?:sı)?\s+yap\b", re.IGNORECASE),
    re.compile(r"\bweb(?:'|’)?de\s+ara(?:ştır)?\b", re.IGNORECASE),
    re.compile(r"\bweb\s+ara\b", re.IGNORECASE),
    re.compile(r"\binternet(?:te|ten)?\s+(?:ara|araştır|bak)\b", re.IGNORECASE),
    re.compile(r"\binternet\s+araması\s+yap\b", re.IGNORECASE),
)
QUERY_FILLER_PATTERN = re.compile(
    r"\b(?:orlin|bana|lütfen|bir|şu\s+konuda|konusunda)\b",
    re.IGNORECASE,
)


class WebSearchError(RuntimeError):
    """Raised when an explicitly requested web search cannot be completed."""


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


class _HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_text(value: str, limit: int) -> str:
    parser = _HTMLTextParser()
    parser.feed(unescape(value))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()[:limit]


def is_web_search_request(content: str) -> bool:
    return any(pattern.search(content) for pattern in SEARCH_PATTERNS)


def extract_web_search_query(content: str) -> str | None:
    if not is_web_search_request(content):
        return None
    query = content
    for pattern in SEARCH_PATTERNS:
        query = pattern.sub(" ", query)
    query = QUERY_FILLER_PATTERN.sub(" ", query)
    return re.sub(r"\s+", " ", query).strip(" \t\r\n.,!?;:-")


def _parse_search_results(xml_content: str) -> list[WebSearchResult]:
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as error:
        raise WebSearchError("Arama sağlayıcısı geçerli sonuç döndürmedi.") from error

    results: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    for item in root.findall("./channel/item"):
        title = _plain_text(item.findtext("title", ""), 250)
        url = item.findtext("link", "").strip()
        snippet = _plain_text(item.findtext("description", ""), 700)
        parsed_url = urlsplit(url)
        hostname = parsed_url.hostname or ""
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            is_local_host = (
                hostname.casefold() == "localhost"
                or hostname.casefold().endswith((".localhost", ".local"))
            )
        else:
            is_local_host = not address.is_global
        if (
            not title
            or not snippet
            or parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or parsed_url.username is not None
            or parsed_url.password is not None
            or is_local_host
            or url in seen_urls
        ):
            continue
        results.append(WebSearchResult(title, url, snippet))
        seen_urls.add(url)
        if len(results) >= SEARCH_RESULT_LIMIT:
            break
    return results


async def search_web(query: str) -> list[WebSearchResult]:
    query = query.strip()
    if not query:
        raise ValueError("Web araması için boş olmayan bir sorgu gerekli.")

    try:
        async with httpx.AsyncClient(
            timeout=SEARCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": "OrlinDiscordBot/1.0"},
        ) as client:
            response = await client.get(
                "https://www.bing.com/search",
                params={"format": "rss", "q": query[:300]},
            )
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise WebSearchError("Bing web aramasına şu anda erişilemiyor.") from error

    return _parse_search_results(response.text)
