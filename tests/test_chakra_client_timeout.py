"""Tests for idle-based timeout semantics in ChakraClient.iter_events."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from client.chakra_client import ChakraClient, EventType, ServerEvent


def _done_event() -> ServerEvent:
    return ServerEvent(type=EventType.DONE, full_text="ok")


def _text_event(text: str = "hi") -> ServerEvent:
    return ServerEvent(type=EventType.TEXT_CHUNK, text=text)


def test_iter_events_times_out_on_idle() -> None:
    client = ChakraClient.__new__(ChakraClient)
    client._events = []
    client._stream_error = None
    client._stream_closed = __import__("threading").Event()
    client._event_lock = __import__("threading").Lock()

    times = iter([0.0, 0.1, 5.0])

    with (
        patch("client.chakra_client.time.monotonic", side_effect=lambda: next(times)),
        patch("client.chakra_client.time.sleep"),
    ):
        with pytest.raises(TimeoutError, match="Timed out waiting for server events"):
            list(client.iter_events(timeout_seconds=1.0))


def test_iter_events_resets_idle_on_each_event() -> None:
    client = ChakraClient.__new__(ChakraClient)
    client._events = [_text_event("a"), _text_event("b"), _done_event()]
    client._stream_error = None
    client._stream_closed = __import__("threading").Event()
    client._event_lock = __import__("threading").Lock()

    # Total elapsed 10s, but events at 0, 4, 8 — each gap < 3s idle limit.
    times = iter([0.0, 0.0, 4.0, 4.0, 8.0, 8.0, 10.0, 10.0])

    with (
        patch("client.chakra_client.time.monotonic", side_effect=lambda: next(times)),
        patch("client.chakra_client.time.sleep"),
    ):
        events = list(client.iter_events(timeout_seconds=3.0))

    assert [e.type for e in events] == [
        EventType.TEXT_CHUNK,
        EventType.TEXT_CHUNK,
        EventType.DONE,
    ]


def test_iter_events_unbounded_when_timeout_none() -> None:
    client = ChakraClient.__new__(ChakraClient)
    client._events = [_done_event()]
    client._stream_error = None
    client._stream_closed = __import__("threading").Event()
    client._event_lock = __import__("threading").Lock()

    with patch("client.chakra_client.time.sleep"):
        events = list(client.iter_events(timeout_seconds=None))

    assert len(events) == 1
    assert events[0].type == EventType.DONE
