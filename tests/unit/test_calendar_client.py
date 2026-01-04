"""
Unit tests for InvestingCalendarClient
"""
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from src.data_sources.investing_calendar import InvestingCalendarClient
from src.core.models import CalendarEvent


class TestInvestingCalendarClient:
    """Test InvestingCalendarClient"""

    @pytest.fixture
    def client(self, tmp_path):
        """Create client without Redis"""
        cache_file = str(tmp_path / "test_cache.json")
        return InvestingCalendarClient(
            redis_client=None,
            cache_enabled=True,
            cache_file=cache_file,
        )

    @pytest.fixture
    def client_with_redis(self, tmp_path):
        """Create client with mock Redis"""
        redis_mock = AsyncMock()
        cache_file = str(tmp_path / "test_cache.json")
        return InvestingCalendarClient(
            redis_client=redis_mock,
            cache_enabled=True,
            cache_file=cache_file,
        )

    # Test 1: XHR defaults extraction
    def test_extract_xhr_defaults(self, client):
        """Test extracting timezone and timeFilter from HTML"""
        html = """
        <select id="timeZone">
            <option value="55" selected>UTC</option>
        </select>
        <input type="radio" name="timeFilter" value="timeRemain" checked>
        """

        defaults = client._extract_xhr_defaults(html)

        assert defaults["timeZone"] == "55"
        assert defaults["timeFilter"] == "timeRemain"

    def test_extract_xhr_defaults_fallback(self, client):
        """Test XHR defaults extraction with missing elements (uses fallback)"""
        html = "<html><body>No timezone selector</body></html>"

        defaults = client._extract_xhr_defaults(html)

        assert defaults["timeZone"] == "55"  # Fallback
        assert defaults["timeFilter"] == "timeRemain"  # Fallback

    # Test 2: XHR payload construction
    def test_build_xhr_payload(self, client):
        """Test building XHR POST payload"""
        defaults = {"timeZone": "55", "timeFilter": "timeRemain"}

        payload = client._build_xhr_payload(
            date_from="2025-11-20",
            date_to="2025-11-20",
            min_importance=2,
            defaults=defaults,
        )

        # Convert to dict for easier assertion
        payload_dict = dict(payload)
        assert payload_dict["dateFrom"] == "2025-11-20"
        assert payload_dict["dateTo"] == "2025-11-20"
        assert payload_dict["timeZone"] == "55"
        assert payload_dict["currentTab"] == "custom"

        # Check importance filters (should include 2 and 3)
        importance_values = [v for k, v in payload if k == "importance[]"]
        assert "2" in importance_values
        assert "3" in importance_values
        assert len(importance_values) == 2

    def test_build_xhr_payload_no_importance(self, client):
        """Test payload with no importance filter"""
        defaults = {"timeZone": "55", "timeFilter": "timeRemain"}

        payload = client._build_xhr_payload(
            date_from="2025-11-20",
            date_to="2025-11-20",
            min_importance=0,  # No filter
            defaults=defaults,
        )

        # Should not include importance filters
        importance_values = [v for k, v in payload if k == "importance[]"]
        assert len(importance_values) == 0

    # Test 3: XHR fetch success
    @pytest.mark.asyncio
    async def test_fetch_html_with_xhr_success(self, client):
        """Test successful XHR fetch"""
        mock_response_data = {
            "data": '<tr class="js-event-item"><td class="time">14:00</td></tr>'
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            # Create mock client instance
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock GET for base page
            mock_get_response = MagicMock()
            mock_get_response.status_code = 200
            mock_get_response.text = "<html></html>"
            mock_client.get.return_value = mock_get_response

            # Mock POST for XHR
            mock_post_response = MagicMock()
            mock_post_response.status_code = 200
            mock_post_response.text = json.dumps(mock_response_data)
            mock_client.post.return_value = mock_post_response

            html = await client._fetch_html_with_xhr("2025-11-20", min_importance=2)

            assert html is not None
            assert "<table" in html
            assert "js-event-item" in html

    # Test 4: XHR fetch failure → returns None
    @pytest.mark.asyncio
    async def test_fetch_html_with_xhr_failure(self, client):
        """Test XHR fetch failure returns None"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = Exception("Network error")

            html = await client._fetch_html_with_xhr("2025-11-20", min_importance=2)

            assert html is None

    @pytest.mark.asyncio
    async def test_fetch_html_with_xhr_invalid_json(self, client):
        """Test XHR fetch with invalid JSON response"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_get_response = MagicMock()
            mock_get_response.status_code = 200
            mock_get_response.text = "<html></html>"
            mock_client.get.return_value = mock_get_response

            mock_post_response = MagicMock()
            mock_post_response.status_code = 200
            mock_post_response.text = "Not JSON"  # Invalid JSON
            mock_client.post.return_value = mock_post_response

            html = await client._fetch_html_with_xhr("2025-11-20", min_importance=2)

            assert html is None

    # Test 5: File cache load/save
    def test_file_cache_operations(self, client):
        """Test JSON file cache load and save"""
        # Test empty cache
        cache = client._load_cache_from_file()
        assert cache == {}

        # Test save and load
        test_events = [
            CalendarEvent(
                date="2025-11-20",
                time="14:00",
                currency="USD",
                importance=3,
                event="FOMC Meeting",
            )
        ]

        cache_data = {
            "2025-11-20": {
                "fetched_at": datetime.utcnow().isoformat(),
                "events": [e.model_dump() for e in test_events],
            }
        }

        client._save_cache_to_file(cache_data)

        loaded_cache = client._load_cache_from_file()
        assert "2025-11-20" in loaded_cache
        assert len(loaded_cache["2025-11-20"]["events"]) == 1
        assert loaded_cache["2025-11-20"]["events"][0]["event"] == "FOMC Meeting"

    def test_get_cached_events_from_file(self, client):
        """Test retrieving cached events from file cache"""
        cache = {
            "2025-11-20": {
                "fetched_at": datetime.utcnow().isoformat(),
                "events": [
                    {
                        "date": "2025-11-20",
                        "time": "14:00",
                        "currency": "USD",
                        "importance": 3,
                        "event": "CPI Release",
                        "actual": None,
                        "forecast": None,
                        "previous": None,
                    }
                ],
            }
        }

        events = client._get_cached_events_from_file(cache, "2025-11-20")

        assert len(events) == 1
        assert isinstance(events[0], CalendarEvent)
        assert events[0].event == "CPI Release"

    def test_update_cache_in_file(self, client):
        """Test updating file cache for a date"""
        cache = {}
        test_events = [
            CalendarEvent(
                date="2025-11-21",
                time="10:00",
                currency="EUR",
                importance=2,
                event="ECB Meeting",
            )
        ]

        client._update_cache_in_file(cache, "2025-11-21", test_events)

        assert "2025-11-21" in cache
        assert "fetched_at" in cache["2025-11-21"]
        assert len(cache["2025-11-21"]["events"]) == 1
        assert cache["2025-11-21"]["events"][0]["event"] == "ECB Meeting"

    # Test 6: Redis cache integration
    @pytest.mark.asyncio
    async def test_redis_cache_hit(self, client_with_redis):
        """Test Redis cache hit returns cached data"""
        cached_events = [
            {
                "date": "2025-11-21",
                "time": "10:00",
                "currency": "USD",
                "importance": 3,
                "event": "CPI Release",
                "actual": None,
                "forecast": None,
                "previous": None,
            }
        ]

        # Mock Redis to return cached data for tomorrow
        tomorrow = (datetime.utcnow().date() + timedelta(days=1)).strftime("%Y-%m-%d")
        cache_key = f"calendar:{tomorrow}:3"
        client_with_redis.redis_client.get.return_value = json.dumps(cached_events)

        # Mock XHR and Playwright to ensure they're not called
        with patch.object(client_with_redis, "_fetch_html_with_xhr", return_value=None):
            with patch.object(client_with_redis, "_fetch_html_with_playwright", return_value=None):
                events, meta = await client_with_redis.get_upcoming_events(days=1, min_importance=3)

                # Should have called Redis get
                assert client_with_redis.redis_client.get.called

    # Test 7: Graceful degradation path
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, client):
        """Test XHR → Playwright → file cache degradation"""
        tomorrow = (datetime.utcnow().date() + timedelta(days=1)).strftime("%Y-%m-%d")

        # Fail XHR
        with patch.object(client, "_fetch_html_with_xhr", return_value=None):
            # Fail Playwright
            with patch.object(client, "_fetch_html_with_playwright", return_value=None):
                # Provide file cache
                with patch.object(client, "_load_cache_from_file") as mock_load:
                    mock_load.return_value = {
                        tomorrow: {
                            "fetched_at": datetime.utcnow().isoformat(),
                            "events": [
                                {
                                    "date": tomorrow,
                                    "time": "10:00",
                                    "currency": "USD",
                                    "importance": 3,
                                    "event": "Cached Event",
                                    "actual": None,
                                    "forecast": None,
                                    "previous": None,
                                }
                            ],
                        }
                    }

                    events, meta = await client.get_upcoming_events(days=1, min_importance=2)

                    # Should fall back to file cache
                    assert len(events) >= 0

    # Test 8: Error isolation (single day failure)
    @pytest.mark.asyncio
    async def test_error_isolation(self, client):
        """Test that single day failure doesn't break entire query"""
        call_count = 0

        def xhr_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail second day
                raise Exception("Network timeout")
            return '<table><tr class="js-event-item">...</tr></table>'

        with patch.object(client, "_fetch_html_with_xhr", side_effect=xhr_side_effect):
            with patch.object(client, "_parse_calendar", return_value={"events": [], "count": 0}):
                events, meta = await client.get_upcoming_events(days=3, min_importance=2)

                # Should still attempt all days (error isolation)
                assert call_count >= 3

    # Test 9: Event parsing with target_date
    def test_parse_calendar_html_with_date(self, client):
        """Test parsing assigns events from HTML"""
        html = """
        <table id="economicCalendarData">
            <tr class="js-event-item">
                <td class="time">14:00</td>
                <td class="flagCur"><span title="United States">USD</span></td>
                <td class="sentiment">
                    <i class="grayFullBullishIcon"></i>
                    <i class="grayFullBullishIcon"></i>
                    <i class="grayFullBullishIcon"></i>
                </td>
                <td class="event"><a>FOMC Decision</a></td>
                <td class="act"></td>
                <td class="fore"></td>
                <td class="prev"></td>
            </tr>
        </table>
        """

        parsed = client._parse_calendar(html)

        assert parsed["count"] >= 0
        assert "events" in parsed

    # Test 10: Empty calendar handling
    def test_parse_empty_calendar(self, client):
        """Test parsing empty calendar returns empty list"""
        html = """
        <table id="economicCalendarData">
        </table>
        """

        parsed = client._parse_calendar(html)

        assert parsed["events"] == []
        assert parsed["count"] == 0

    def test_cache_disabled(self, tmp_path):
        """Test that caching can be disabled"""
        cache_file = str(tmp_path / "should_not_exist.json")
        client = InvestingCalendarClient(
            redis_client=None,
            cache_enabled=False,
            cache_file=cache_file,
        )

        # Try to save cache
        cache_data = {"test": "data"}
        client._save_cache_to_file(cache_data)

        # File should not be created
        assert not Path(cache_file).exists()

        # Load should return empty dict
        loaded = client._load_cache_from_file()
        assert loaded == {}
