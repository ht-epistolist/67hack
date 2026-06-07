"""A tiny async pub/sub bus. Agents publish investigation events; the WebSocket
endpoint subscribes and forwards them to the UI. Decoupled so the agent code
never imports FastAPI.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict:
        return {"type": self.type, "ts": self.ts, **self.payload}


class EventBus:
    """Fan-out bus: every subscriber gets its own queue + a replayable history
    so a late-connecting UI still sees the whole investigation."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []
        self.history: list[dict] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def publish(self, type: str, **payload: Any) -> None:
        evt = Event(type=type, payload=payload).to_dict()
        self.history.append(evt)
        for q in list(self._subscribers):
            await q.put(evt)

    def reset(self) -> None:
        self.history.clear()


# Process-wide bus for the single-investigation demo.
bus = EventBus()
