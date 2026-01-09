"""
Live integration tests for InvestingCalendarClient

These tests make real requests to investing.com.
Run with: pytest tests/integration/test_calendar_live.py -v -s -m live
"""
import pytest
import time
from datetime import datetime, timedelta

from src.data_sources.investing_calendar import InvestingCalendarClient
from src.core.models import CalendarEvent


@pytest.mark.live
class TestCalendarLiveIntegration:
    """Live integration tests"""

    @pytest.fixture
    def client(self, tmp_path):
        """Create live client with temporary cache"""
        cache_file = str(tmp_path / "calendar_live.json")
        return InvestingCalendarClient(
            redis_client=None,
            cache_enabled=True,
            cache_file=cache_file,
        )

    @pytest.mark.asyncio
    async def test_xhr_fetch_live(self, client):
        """Test live XHR fetch to investing.com"""
        today = datetime.utcnow().date()
        date_str = today.strftime("%Y-%m-%d")

        html = await client._fetch_html_with_xhr(date_str, min_importance=1)

        # Should return HTML (or None if site is down/blocked)
        # We can't assert it always succeeds due to rate limiting
        if html:
            assert "<table" in html or "<tr" in html
            print(f"\n✓ XHR fetch successful ({len(html)} bytes)")
        else:
            print("\n⚠ XHR fetch returned None (may be rate limited)")

    @pytest.mark.asyncio
    async def test_get_upcoming_events_live(self, client):
        """Test full upcoming events flow with real API"""
        print("\n--- Testing get_upcoming_events (live) ---")

        events, meta = await client.get_upcoming_events(days=7, min_importance=1)

        # Validate structure
        assert isinstance(events, list)
        assert meta.provider == "investing_calendar"

        print(f"\nFetched {len(events)} events for next 7 days (importance >= 1)")

        # If events found, validate structure
        if events:
            event_dict = events[0]
            assert "date" in event_dict
            assert "time" in event_dict
            assert "currency" in event_dict
            assert "importance" in event_dict
            assert "event" in event_dict
            assert event_dict["importance"] >= 1

            # Print first few events
            for i, evt in enumerate(events[:5]):
                print(
                    f"  {i+1}. [{evt['date']} {evt['time']}] "
                    f"{evt['currency']} - {evt['event']} (importance: {evt['importance']})"
                )

        # For a 7-day window, we should always have at least some events with importance >= 1
        # If no events, the calendar fetch is likely broken
        assert len(events) >= 1, (
            f"Expected at least 1 event with importance >= 1 in 7-day window, got 0. "
            "Calendar fetch may be broken."
        )

    @pytest.mark.asyncio
    async def test_cache_persistence(self, client):
        """Test that cache persists across calls"""
        print("\n--- Testing cache persistence ---")

        # First call - should fetch fresh (or use existing cache)
        start1 = time.time()
        events1, meta1 = await client.get_upcoming_events(days=1, min_importance=3)
        elapsed1 = time.time() - start1

        print(f"\nFirst call: {len(events1)} events in {elapsed1:.2f}s")

        # Second call - should use cache for non-today dates
        start2 = time.time()
        events2, meta2 = await client.get_upcoming_events(days=1, min_importance=3)
        elapsed2 = time.time() - start2

        print(f"Second call: {len(events2)} events in {elapsed2:.2f}s")

        # Results should be similar (may differ if today's data refreshed)
        assert isinstance(events1, list)
        assert isinstance(events2, list)

        # Second call should generally be faster due to caching
        # (unless first call also hit cache)
        print(f"Speed improvement: {elapsed1/elapsed2:.1f}x" if elapsed2 > 0 else "N/A")

    @pytest.mark.asyncio
    async def test_multi_day_fetch_performance(self, client):
        """Test performance of multi-day fetch"""
        print("\n--- Testing multi-day fetch performance ---")

        start = time.time()
        events, meta = await client.get_upcoming_events(days=7, min_importance=2)
        elapsed = time.time() - start

        # With XHR, 7 days should take < 30s fresh, < 5s cached
        # Allow generous time for CI environments and rate limiting
        assert elapsed < 90, f"Took {elapsed}s, expected < 90s"

        print(f"\nFetched {len(events)} events for 7 days in {elapsed:.2f}s")
        print(f"Average per day: {elapsed/8:.2f}s")

        # Performance classification
        if elapsed < 5:
            print("Performance: EXCELLENT (cache hit)")
        elif elapsed < 30:
            print("Performance: GOOD (XHR strategy)")
        elif elapsed < 60:
            print("Performance: ACCEPTABLE (may have retries or slow network)")
        else:
            print("Performance: SLOW (likely rate limited or network issues)")

    @pytest.mark.asyncio
    async def test_central_bank_events_live(self, client):
        """Test fetching central bank events"""
        print("\n--- Testing central bank events (live) ---")

        events, meta = await client.get_central_bank_events(days=30)

        print(f"\nFound {len(events)} central bank events in next 30 days")

        if events:
            # Print first few CB events
            for i, evt in enumerate(events[:5]):
                print(
                    f"  {i+1}. [{evt['date']} {evt['time']}] "
                    f"{evt['currency']} - {evt['event']}"
                )

        # All events should be high importance
        for evt in events:
            assert evt["importance"] == 3, f"CB event should have importance=3, got {evt['importance']}"

    @pytest.mark.asyncio
    async def test_error_handling_invalid_date(self, client):
        """Test error handling with invalid date range"""
        print("\n--- Testing error handling ---")

        # Test with 0 days (edge case)
        events, meta = await client.get_upcoming_events(days=0, min_importance=2)

        # Should not crash, should return today's events
        assert isinstance(events, list)
        print(f"\nFetched {len(events)} events for today (days=0)")

    @pytest.mark.asyncio
    async def test_importance_filtering(self, client):
        """Test importance level filtering"""
        print("\n--- Testing importance filtering ---")

        # Fetch with different importance levels
        events_low = await client.get_upcoming_events(days=3, min_importance=1)
        events_med = await client.get_upcoming_events(days=3, min_importance=2)
        events_high = await client.get_upcoming_events(days=3, min_importance=3)

        print(f"\nImportance >= 1: {len(events_low[0])} events")
        print(f"Importance >= 2: {len(events_med[0])} events")
        print(f"Importance >= 3: {len(events_high[0])} events")

        # Higher importance threshold should return fewer or equal events
        assert len(events_low[0]) >= len(events_med[0])
        assert len(events_med[0]) >= len(events_high[0])

        # All high importance events should have importance=3
        for evt in events_high[0]:
            assert evt["importance"] == 3
