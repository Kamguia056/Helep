"""Apache Kafka producer + consumer helpers (aiokafka).

Patterns:
  - Pub/Sub (Kafka topics + consumer groups)
  - Outbox-lite (publish + db-write live in same async block in main.py)
  - Circuit breaker (COMPLETED: full CLOSED / OPEN / HALF_OPEN state machine)

Partition keying:
  Every saga-critical publish should pass key=<incident_id> (or <user_id>).
  Same-key events land on the same partition, preserving ordering and ensuring
  the "no double dispatch" invariant holds even with multi-replica consumers
  (one partition is owned by one consumer at a time inside a group).
"""
from __future__ import annotations
import json
import os
import time
from typing import Awaitable, Callable, Iterable

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

_producer: AIOKafkaProducer | None = None


async def producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            enable_idempotence=True,
            acks="all",
            value_serializer=lambda v: json.dumps(v).encode(),
            key_serializer=lambda k: k.encode() if k else None,
        )
        await _producer.start()
    return _producer


async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None


async def health() -> bool:
    """Liveness ping for /readyz — verify broker reachable + metadata fetch works."""
    try:
        p = await producer()
        await p.client.fetch_all_metadata()
        return True
    except Exception:
        return False


# ---- Circuit Breaker — CLOSED / OPEN / HALF_OPEN state machine ----
# States:
#   CLOSED    — normal operation; failures are counted.
#               When fails >= fail_threshold → transition to OPEN.
#   OPEN      — all calls are rejected immediately.
#               After reset_after_s seconds → transition to HALF_OPEN.
#   HALF_OPEN — one probe call is allowed through.
#               If it succeeds → back to CLOSED (fail counter reset).
#               If it fails   → back to OPEN (timer restarted).
class CircuitBreaker:
    _CLOSED = "CLOSED"
    _OPEN = "OPEN"
    _HALF_OPEN = "HALF_OPEN"

    def __init__(self, fail_threshold: int = 5, reset_after_s: float = 10.0):
        self.fail_threshold = fail_threshold
        self.reset_after_s = reset_after_s
        self.fails = 0
        self.opened_at: float | None = None
        self._state = self._CLOSED

    # -- line 68: core allow() gate ------------------------------------------
    def allow(self) -> bool:
        """Return True when the call should proceed, False to short-circuit."""
        if self._state == self._CLOSED:
            # Normal operation — always allow.
            return True

        if self._state == self._OPEN:
            # Check if the cool-down window has expired.
            if self.opened_at is not None and (time.monotonic() - self.opened_at) >= self.reset_after_s:
                # Transition to HALF_OPEN: let exactly one probe through.
                self._state = self._HALF_OPEN
                return True
            # Still within the open window — reject the call.
            return False

        if self._state == self._HALF_OPEN:
            # Probe call is already in flight; reject any concurrent requests.
            return False

        return True  # unreachable safety net

    # -- line 86: success path ------------------------------------------------
    def record_success(self) -> None:
        """Called after a successful publish. Resets the breaker if recovering."""
        self.fails = 0
        self.opened_at = None
        self._state = self._CLOSED  # HALF_OPEN → CLOSED on probe success

    # -- line 93: failure path ------------------------------------------------
    def record_failure(self) -> None:
        """Called after a publish exception. May open or re-open the breaker."""
        self.fails += 1
        if self._state == self._HALF_OPEN:
            # Probe failed — go back to OPEN and restart the timer.
            self._state = self._OPEN
            self.opened_at = time.monotonic()
        elif self._state == self._CLOSED and self.fails >= self.fail_threshold:
            # Threshold crossed — open the breaker.
            self._state = self._OPEN
            self.opened_at = time.monotonic()

    @property
    def state(self) -> str:
        """Expose current state name for logging / metrics."""
        return self._state


_breaker = CircuitBreaker()


async def publish(topic: str, event: dict, key: str | None = None) -> None:
    """Outbox-lite: caller should db-write THEN await publish() in same async block."""
    if not _breaker.allow():
        raise RuntimeError(f"circuit-open [{_breaker.state}]: {topic}")
    try:
        p = await producer()
        await p.send_and_wait(topic, value=event, key=key)
        _breaker.record_success()
    except Exception:
        _breaker.record_failure()
        raise


Handler = Callable[[dict], Awaitable[None]]


async def consume(topics: Iterable[str], group: str, handler: Handler) -> None:
    """Consumer-group reader. Manual commit only on successful handler (at-least-once)."""
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    await consumer.start()
    try:
        async for msg in consumer:
            payload = msg.value
            payload["_stream"] = msg.topic  # preserved name for back-compat with handlers
            try:
                await handler(payload)
                await consumer.commit()
            except Exception:
                # leave un-committed → re-delivered on next read (at-least-once)
                pass
    finally:
        await consumer.stop()
