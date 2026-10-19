import pytest

from ink_ai_discord.web_search import WebSearchError, _parse_search_results


def test_search_results_are_cleaned_and_only_http_urls_are_kept() -> None:
    results = _parse_search_results(
        """<?xml version="1.0"?>
        <rss><channel>
          <item>
            <title>Enerji &amp; Gelecek</title>
            <link>https://example.com/energy</link>
            <description>&lt;b&gt;Yeni&lt;/b&gt; enerji verisi</description>
          </item>
          <item>
            <title>Local target</title>
            <link>http://127.0.0.1/private</link>
            <description>Not a public source</description>
          </item>
        </channel></rss>"""
    )

    assert len(results) == 1
    assert results[0].title == "Enerji & Gelecek"
    assert results[0].url == "https://example.com/energy"
    assert results[0].snippet == "Yeni enerji verisi"


def test_invalid_search_provider_xml_fails_explicitly() -> None:
    with pytest.raises(WebSearchError, match="geçerli sonuç"):
        _parse_search_results("<invalid")
