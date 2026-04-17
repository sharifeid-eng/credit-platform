"""
Event Bus — Lightweight synchronous pub/sub for knowledge system events.

Enables the "one input, many updates" pattern: a single event (tape ingested,
document added, memo edited) fans out to multiple listeners that update
knowledge nodes, check thesis drift, extract learning rules, etc.

No external dependencies. Synchronous by design — listeners do file I/O only,
never AI calls (those are queued for background processing).

Usage:
    from core.mind.event_bus import event_bus, Events

    # Register a listener
    @event_bus.on(Events.TAPE_INGESTED)
    def on_tape(payload):
        # payload is a dict with event-specific data
        ...

    # Publish an event
    event_bus.publish(Events.TAPE_INGESTED, {
        "company": "klaim",
        "product": "UAE_healthcare",
        "snapshot": "2026-03-03_uae_healthcare.csv",
        "metrics": {...},
    })

    # Disable for tests
    event_bus.disable()
    event_bus.enable()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Events:
    """Event type constants."""

    TAPE_INGESTED = "tape_ingested"
    DOCUMENT_INGESTED = "document_ingested"
    MEMO_EDITED = "memo_edited"
    CORRECTION_RECORDED = "correction_recorded"
    THESIS_UPDATED = "thesis_updated"
    SNAPSHOT_LOADED = "snapshot_loaded"
    MIND_ENTRY_CREATED = "mind_entry_created"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    COVENANT_BREACH_DETECTED = "covenant_breach_detected"
    AGENT_FINDING = "agent_finding"
    MEMO_GENERATED = "memo_generated"


# Type alias for event handlers
EventHandler = Callable[[Dict[str, Any]], None]


class EventBus:
    """Lightweight synchronous event bus.

    Listeners are called in registration order. Exceptions in one listener
    don't prevent others from running (logged and swallowed).
    """

    def __init__(self):
        self._listeners: Dict[str, List[EventHandler]] = {}
        self._enabled: bool = True
        self._event_log: List[Dict[str, Any]] = []  # in-memory log for debugging
        self._max_log_size: int = 100

    def on(self, event_type: str) -> Callable:
        """Decorator to register a listener for an event type.

        Usage:
            @event_bus.on(Events.TAPE_INGESTED)
            def handle_tape(payload):
                ...
        """
        def decorator(fn: EventHandler) -> EventHandler:
            self.subscribe(event_type, fn)
            return fn
        return decorator

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        self._listeners.setdefault(event_type, [])
        if handler not in self._listeners[event_type]:
            self._listeners[event_type].append(handler)
            logger.debug(
                "EventBus: registered %s for %s",
                handler.__name__, event_type
            )

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler for an event type."""
        if event_type in self._listeners:
            try:
                self._listeners[event_type].remove(handler)
            except ValueError:
                pass

    def publish(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> int:
        """Publish an event to all registered listeners.

        Args:
            event_type: The event type string.
            payload: Event-specific data dict.

        Returns:
            Number of listeners that were called.
        """
        if not self._enabled:
            return 0

        payload = payload or {}
        handlers = self._listeners.get(event_type, [])

        if not handlers:
            logger.debug("EventBus: no listeners for %s", event_type)
            return 0

        # Log the event
        self._log_event(event_type, payload, len(handlers))

        called = 0
        for handler in handlers:
            try:
                handler(payload)
                called += 1
            except Exception as e:
                logger.error(
                    "EventBus: listener %s failed for %s: %s",
                    handler.__name__, event_type, e,
                    exc_info=True,
                )

        logger.debug(
            "EventBus: published %s → %d/%d listeners",
            event_type, called, len(handlers),
        )
        return called

    def _log_event(self, event_type: str, payload: Dict, listener_count: int) -> None:
        """Append to in-memory event log (bounded)."""
        self._event_log.append({
            "event_type": event_type,
            "payload_keys": list(payload.keys()),
            "listener_count": listener_count,
        })
        # Trim to max size
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

    def disable(self) -> None:
        """Disable event publishing. Use in tests to prevent side effects."""
        self._enabled = False
        logger.debug("EventBus: disabled")

    def enable(self) -> None:
        """Re-enable event publishing."""
        self._enabled = True
        logger.debug("EventBus: enabled")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def clear(self) -> None:
        """Remove all listeners. Use in tests for clean state."""
        self._listeners.clear()
        self._event_log.clear()

    def get_listeners(self, event_type: str) -> List[EventHandler]:
        """Get registered listeners for an event type (for debugging)."""
        return list(self._listeners.get(event_type, []))

    def get_event_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent events from the in-memory log."""
        return self._event_log[-limit:]

    @property
    def stats(self) -> Dict[str, Any]:
        """Summary stats for debugging."""
        return {
            "enabled": self._enabled,
            "event_types": list(self._listeners.keys()),
            "total_listeners": sum(len(v) for v in self._listeners.values()),
            "events_logged": len(self._event_log),
        }


# --------------------------------------------------------------------------
# Global singleton
# --------------------------------------------------------------------------

event_bus = EventBus()
