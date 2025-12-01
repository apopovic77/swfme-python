"""
Unit tests for Event Bus
"""

import pytest
import asyncio
from swfme.monitoring.event_bus import EventBus


class TestEventBus:
    """Test Event Bus functionality"""

    def setup_method(self):
        """Setup for each test"""
        self.event_bus = EventBus()

    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self):
        """Test subscribing to events and emitting"""
        received_events = []

        async def handler(event):
            received_events.append(event)

        # Subscribe
        self.event_bus.subscribe("test.event", handler)

        # Emit
        await self.event_bus.emit({
            "type": "test.event",
            "data": "test data"
        })

        # Check received
        assert len(received_events) == 1
        assert received_events[0]["type"] == "test.event"
        assert received_events[0]["data"] == "test data"

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self):
        """Test wildcard subscription (all events)"""
        received_events = []

        async def handler(event):
            received_events.append(event)

        # Subscribe to all events
        self.event_bus.subscribe("*", handler)

        # Emit different event types
        await self.event_bus.emit({"type": "event1"})
        await self.event_bus.emit({"type": "event2"})
        await self.event_bus.emit({"type": "event3"})

        # Should receive all
        assert len(received_events) == 3

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Test multiple subscribers for same event"""
        handler1_calls = []
        handler2_calls = []

        async def handler1(event):
            handler1_calls.append(event)

        async def handler2(event):
            handler2_calls.append(event)

        # Subscribe both
        self.event_bus.subscribe("test.event", handler1)
        self.event_bus.subscribe("test.event", handler2)

        # Emit
        await self.event_bus.emit({"type": "test.event"})

        # Both should receive
        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Test unsubscribing from events"""
        received_events = []

        async def handler(event):
            received_events.append(event)

        # Subscribe
        self.event_bus.subscribe("test.event", handler)

        # Emit
        await self.event_bus.emit({"type": "test.event"})
        assert len(received_events) == 1

        # Unsubscribe
        self.event_bus.unsubscribe("test.event", handler)

        # Emit again
        await self.event_bus.emit({"type": "test.event"})

        # Should not receive second event
        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_event_history(self):
        """Test event logging"""
        # Emit some events
        await self.event_bus.emit({"type": "event1", "data": "a"})
        await self.event_bus.emit({"type": "event2", "data": "b"})
        await self.event_bus.emit({"type": "event1", "data": "c"})

        # Get all events
        all_events = self.event_bus.get_events()
        assert len(all_events) == 3

        # Get filtered by type
        event1_only = self.event_bus.get_events(event_type="event1")
        assert len(event1_only) == 2
        assert all(e["type"] == "event1" for e in event1_only)

    @pytest.mark.asyncio
    async def test_event_limit(self):
        """Test event history limit"""
        # Emit many events
        for i in range(10):
            await self.event_bus.emit({"type": "test", "index": i})

        # Get with limit
        limited = self.event_bus.get_events(limit=5)
        assert len(limited) == 5

    @pytest.mark.asyncio
    async def test_auto_timestamp(self):
        """Test automatic timestamp addition"""
        await self.event_bus.emit({"type": "test"})

        events = self.event_bus.get_events()
        assert "timestamp" in events[0]

    @pytest.mark.asyncio
    async def test_handler_error_handling(self):
        """Test that handler errors don't break event bus"""
        working_handler_calls = []

        async def failing_handler(event):
            raise Exception("Handler error")

        async def working_handler(event):
            working_handler_calls.append(event)

        # Subscribe both
        self.event_bus.subscribe("test", failing_handler)
        self.event_bus.subscribe("test", working_handler)

        # Emit - should not raise despite failing handler
        await self.event_bus.emit({"type": "test"})

        # Working handler should still be called
        assert len(working_handler_calls) == 1

    def test_clear_history(self):
        """Test clearing event history"""
        # Add some events (sync method for simplicity)
        self.event_bus._event_log.append({"type": "test1"})
        self.event_bus._event_log.append({"type": "test2"})

        assert len(self.event_bus._event_log) > 0

        # Clear
        self.event_bus.clear_history()

        assert len(self.event_bus._event_log) == 0

    def test_get_stats(self):
        """Test getting event bus stats"""
        # Add subscriber
        async def handler(event):
            pass

        self.event_bus.subscribe("test1", handler)
        self.event_bus.subscribe("test2", handler)
        self.event_bus.subscribe("*", handler)

        stats = self.event_bus.get_stats()

        assert "total_events" in stats
        assert "subscriber_count" in stats
        assert stats["subscriber_count"] == 3  # 3 subscriptions
