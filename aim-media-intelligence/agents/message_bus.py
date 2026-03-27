"""
Simple in-process message bus for inter-agent communication.
Agents publish events and subscribe to each other's outputs.
"""
import threading
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class Message:
    sender: str
    event: str
    payload: Any
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MessageBus:
    """Thread-safe pub/sub message bus for agent coordination."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._history: list[Message] = []
        self._lock = threading.Lock()

    def subscribe(self, event: str, handler: Callable):
        with self._lock:
            self._subscribers[event].append(handler)

    def publish(self, sender: str, event: str, payload: Any = None):
        msg = Message(sender=sender, event=event, payload=payload)
        with self._lock:
            self._history.append(msg)
            handlers = list(self._subscribers.get(event, []))
        logger.debug(f"[Bus] {sender} → {event}")
        for handler in handlers:
            try:
                handler(msg)
            except Exception as e:
                logger.error(f"Handler error for event '{event}': {e}")

    def get_history(self, event: str = None) -> list[Message]:
        with self._lock:
            if event:
                return [m for m in self._history if m.event == event]
            return list(self._history)

    def last(self, event: str) -> Message | None:
        history = self.get_history(event)
        return history[-1] if history else None
