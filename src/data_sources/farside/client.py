"""
Farside ETF flow data client (HTML/CSV parsing).
"""
import csv
from html.parser import HTMLParser
from io import StringIO
from typing import Any, Dict, List, Optional

from src.core.models import SourceMeta
from src.core.source_meta import SourceMetaBuilder
from src.data_sources.base import BaseDataSource


class _HtmlTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.rows: List[List[str]] = []
        self._current_row: List[str] = []
        self._cell_buffer: List[str] = []
        self._table_found = False

    def handle_starttag(self, tag: str, attrs):
        if tag == "table" and not self._table_found:
            self.in_table = True
            self._table_found = True
        elif self.in_table and tag == "tr":
            self.in_row = True
            self._current_row = []
        elif self.in_table and tag in {"td", "th"}:
            self.in_cell = True
            self._cell_buffer = []

    def handle_endtag(self, tag: str):
        if self.in_table and tag in {"td", "th"}:
            cell_text = "".join(self._cell_buffer).strip()
            self._current_row.append(cell_text)
            self._cell_buffer = []
            self.in_cell = False
        elif self.in_table and tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = []
            self.in_row = False
        elif tag == "table" and self.in_table:
            self.in_table = False

    def handle_data(self, data: str):
        if self.in_cell:
            self._cell_buffer.append(data)


def _parse_html_table(html: str) -> Dict[str, Any]:
    parser = _HtmlTableParser()
    parser.feed(html)
    rows = parser.rows
    if not rows:
        return {"headers": [], "rows": []}
    headers = rows[0]
    data_rows = rows[1:]
    normalized = []
    for row in data_rows:
        item = {}
        for idx, header in enumerate(headers):
            if idx < len(row):
                item[header] = row[idx]
        if item:
            normalized.append(item)
    return {
        "headers": headers,
        "rows": normalized,
    }


def _parse_csv(text: str) -> Dict[str, Any]:
    reader = csv.DictReader(StringIO(text))
    rows = [row for row in reader]
    return {
        "headers": reader.fieldnames or [],
        "rows": rows,
    }


class FarsideEtfClient(BaseDataSource):
    """Farside ETF flow client (best-effort parsing)."""

    BASE_URL = "https://farside.co.uk"

    def __init__(self):
        super().__init__(
            name="farside",
            base_url=self.BASE_URL,
            timeout=15.0,
            requires_api_key=False,
        )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Accept": "text/html,application/json",
            "User-Agent": "Mozilla/5.0 (compatible; HubriumMCP/1.0)",
        }

    async def fetch_raw(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        base_url_override: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        url = endpoint
        if base_url_override:
            url = f"{base_url_override.rstrip('/')}{endpoint}"
        response = await self.client.get(url, params=params, headers=headers)
        if response.status_code >= 400:
            raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        return raw_data

    async def get_etf_flows(
        self,
        dataset: str = "bitcoin",
        url_override: Optional[str] = None,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        paths = {
            "bitcoin": "/bitcoin-etf-flow/",
            "ethereum": "/ethereum-etf-flow/",
        }
        endpoint = url_override or paths.get(dataset, paths["bitcoin"])

        raw_data = await self.fetch_raw(endpoint)
        if isinstance(raw_data, dict):
            parsed = raw_data
        elif isinstance(raw_data, str) and "," in raw_data.split("\n", 1)[0]:
            parsed = _parse_csv(raw_data)
        else:
            parsed = _parse_html_table(raw_data if isinstance(raw_data, str) else "")

        meta = SourceMetaBuilder.build(
            provider="farside",
            endpoint=endpoint,
            ttl_seconds=3600,
        )
        return parsed, meta
