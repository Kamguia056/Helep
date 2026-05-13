"""Pattern: Strategy. Plug-in matching algorithms for choosing a responder.

Switch via env MATCHER=nearest|credibility|round_robin.
"""
from __future__ import annotations
import itertools
import math
import os
from typing import Iterable, Protocol


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


class Responder(Protocol):
    id: str
    lat: float
    lon: float
    credibility: float


class Matcher(Protocol):
    def pick(self, victim_lat: float, victim_lon: float, responders: Iterable) -> dict | None: ...


class NearestMatcher:
    """Pick the geographically closest free responder using the Haversine formula."""
    def pick(self, victim_lat, victim_lon, responders):
        best = None
        best_d = float("inf")
        for r in responders:
            d = haversine_m(victim_lat, victim_lon, r["lat"], r["lon"])
            if d < best_d:
                best, best_d = r, d
        return {"id": best["id"], "distance_m": best_d} if best else None


class CredibilityWeightedMatcher:
    """Score = credibility / (distance_km + 1). Higher score wins."""
    def pick(self, victim_lat, victim_lon, responders):
        best = None
        best_score = -1.0
        for r in responders:
            d_km = haversine_m(victim_lat, victim_lon, r["lat"], r["lon"]) / 1000.0
            score = r["credibility"] / (d_km + 1.0)
            if score > best_score:
                best, best_score = r, score
        if not best:
            return None
        return {"id": best["id"], "score": best_score}


# -- lines 50-65: RoundRobinMatcher (student-added third strategy) -----------
class RoundRobinMatcher:
    """Distribute incidents evenly across all free responders, ignoring location.

    Uses a module-level cycling iterator so the selection persists across calls
    within the same process lifetime. This prevents any single responder from
    being overloaded when incidents arrive in rapid succession and distances
    are roughly equal (e.g. a single city grid).

    Trade-off vs NearestMatcher: response time may be slightly higher, but
    workload is perfectly balanced — useful for drills or when GPS is imprecise.
    """
    _counter: itertools.cycle | None = None
    _last_ids: list[str] = []

    def pick(self, victim_lat: float, victim_lon: float, responders: Iterable) -> dict | None:
        pool = list(responders)
        if not pool:
            return None
        # Rebuild the cycle only when the responder pool changes.
        ids = [r["id"] for r in pool]
        if ids != self._last_ids:
            self.__class__._last_ids = ids
            self.__class__._counter = itertools.cycle(range(len(pool)))
        idx = next(self.__class__._counter) % len(pool)
        chosen = pool[idx]
        return {"id": chosen["id"], "round_robin_index": idx}


def matcher() -> Matcher:
    name = os.getenv("MATCHER", "nearest").lower()
    if name == "credibility":
        return CredibilityWeightedMatcher()
    if name == "round_robin":
        return RoundRobinMatcher()
    return NearestMatcher()
