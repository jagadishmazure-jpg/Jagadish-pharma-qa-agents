"""Escalation tiers T1–T4 plus confirmation gates.

T1: informational — log and continue.
T2: supervisor review — recorded, no gate.
T3: QA manager approval required (ConfirmationGate).
T4: Qualified Person + documented rationale required (ConfirmationGate).

Batch rejections and critical-deviation closures are always gated.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Tier:
    name: str
    gated: bool
    approver: str


TIERS = {
    "T1": Tier("T1", False, "system"),
    "T2": Tier("T2", False, "supervisor"),
    "T3": Tier("T3", True, "qa_manager"),
    "T4": Tier("T4", True, "qualified_person"),
}

# actions that always require a gate, regardless of tier
ALWAYS_GATED = ("reject_batch", "close_critical_deviation")


class GateError(Exception):
    pass


class ConfirmationGate:
    def __init__(self):
        self.decisions: dict[str, bool] = {}

    def request(self, action: str, detail: str = "") -> str:
        """Open a gate request; returns a token the caller must resolve."""
        token = f"gate-{len(self.decisions) + 1:04d}"
        self.decisions[token] = False
        return token

    def decide(self, token: str, approved: bool) -> None:
        if token not in self.decisions:
            raise GateError(f"unknown gate token: {token}")
        self.decisions[token] = approved

    def check(self, token: str) -> None:
        if not self.decisions.get(token, False):
            raise GateError(f"action blocked: gate {token} not approved")


def tier_for(action: str, severity: str = "minor") -> Tier:
    if action in ALWAYS_GATED:
        return TIERS["T4"] if action == "reject_batch" else TIERS["T3"]
    return {"critical": TIERS["T3"], "major": TIERS["T2"],
            "minor": TIERS["T1"]}.get(severity, TIERS["T1"])
