"""Regulatory-update signal with fake/live backends and explicit gap behavior.

The fake backend returns seeded (fictional) updates. The live backend is a
documented stub: it raises GapError naming exactly what is unavailable
instead of hallucinating updates.
"""

from __future__ import annotations

from dataclasses import dataclass


class GapError(Exception):
    pass


@dataclass
class RegUpdate:
    update_id: str
    source: str
    headline: str
    effective: str


_FAKE_UPDATES = [
    RegUpdate("REG-2026-011", "Intl. Pharma Standards Board",
              "Draft revision: Annex on continuous manufacturing open for comment",
              "2026-11-01"),
    RegUpdate("REG-2026-012", "Intl. Pharma Standards Board",
              "Updated guidance: data-integrity expectations for chromatography systems",
              "2026-10-20"),
]


class FakeRegFeed:
    def latest(self, topic: str = "") -> list[RegUpdate]:
        if topic:
            t = topic.lower()
            return [u for u in _FAKE_UPDATES if t in u.headline.lower()]
        return list(_FAKE_UPDATES)


class LiveRegFeed:
    """Stub for a real regulatory feed. Always raises GapError."""

    def latest(self, topic: str = "") -> list[RegUpdate]:
        raise GapError(
            "live regulatory feed unavailable: no API key configured and no "
            "cached snapshot exists; cannot report updates without a source"
        )
