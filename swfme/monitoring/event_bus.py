"""
Event Bus for sWFME

Central event system for process monitoring and observability.
Supports pub/sub pattern with wildcard subscriptions.
"""

import asyncio
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
from collections import defaultdict


class EventBus:
    """
    Central event bus for process events.

    Features:
    - Subscribe to specific event types or all events (wildcard)
    - Async event handlers
    - Event history/logging
    - Thread-safe operation

    Example:
        >>> async def on_process_completed(event):
        ...     print(f"Process {event['process_name']} completed!")
        ...
        >>> event_bus.subscribe("process.completed", on_process_completed)
        >>> await event_bus.emit({
        ...     "type": "process.completed",
        ...     "process_name": "MyProcess"
        ... })
    """

    def __init__(self, max_history: int = 10000):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_log: List[Dict[str, Any]] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe to event type.

        Args:
            event_type: Event type to subscribe to, or "*" for all events
            callback: Async callback function that receives event dict

        Example:
            >>> async def handler(event):
            ...     print(f"Got event: {event['type']}")
            ...
            >>> event_bus.subscribe("process.completed", handler)
            >>> event_bus.subscribe("*", handler)  # All events
        """
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe from event type"""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    async def emit(self, event: Dict[str, Any]):
        """
        Emit event to all subscribers.

        Args:
            event: Event dictionary (must contain "type" field)

        Example:
            >>> await event_bus.emit({
            ...     "type": "process.started",
            ...     "process_id": "abc-123",
            ...     "process_name": "DataPipeline",
            ...     "timestamp": "2025-01-15T10:30:00Z"
            ... })
        """
        async with self._lock:
            # Add timestamp if not present
            if "timestamp" not in event:
                event["timestamp"] = datetime.utcnow().isoformat()

            # Log event
            self._event_log.append(event)

            # Trim history if needed
            if len(self._event_log) > self._max_history:
                self._event_log = self._event_log[-self._max_history:]

        # Get event type
        event_type = event.get("type", "unknown")

        # Collect handlers
        handlers = []

        # Specific type handlers
        if event_type in self._subscribers:
            handlers.extend(self._subscribers[event_type])

        # Wildcard handlers
        if "*" in self._subscribers:
            handlers.extend(self._subscribers["*"])

        # Execute handlers concurrently
        if handlers:
            await asyncio.gather(
                *[self._call_handler(handler, event) for handler in handlers],
                return_exceptions=True
            )

    async def _call_handler(self, handler: Callable, event: Dict[str, Any]):
        """Call event handler safely"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            print(f"Event handler error: {e}")

    def get_events(
        self,
        process_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get events from history with optional filtering.

        Args:
            process_id: Filter by process ID
            event_type: Filter by event type
            limit: Maximum number of events to return

        Returns:
            List of events (most recent first)

        Example:
            >>> events = event_bus.get_events(process_id="abc-123")
            >>> events = event_bus.get_events(event_type="process.completed", limit=10)
        """
        # Filter events
        events = self._event_log

        if process_id:
            events = [e for e in events if e.get("process_id") == process_id]

        if event_type:
            events = [e for e in events if e.get("type") == event_type]

        # Reverse for most recent first
        events = list(reversed(events))

        # Limit
        if limit:
            events = events[:limit]

        return events

    def clear_history(self):
        """Clear event history"""
        self._event_log.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            "total_events": len(self._event_log),
            "subscriber_count": sum(len(handlers) for handlers in self._subscribers.values()),
            "event_types": list(self._subscribers.keys())
        }

    def __repr__(self) -> str:
        return f"<EventBus events={len(self._event_log)} subscribers={len(self._subscribers)}>"


# Global singleton instance
event_bus = EventBus()
