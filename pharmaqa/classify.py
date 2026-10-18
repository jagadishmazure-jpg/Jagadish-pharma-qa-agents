"""Deviation classifier: critical / major / minor with cited rules.

Rules are evaluated in priority order; the first match wins and every
classification cites the rule ID that fired plus the matched evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# (rule_id, resulting class, predicate description, match function)
_RULES = [
    ("CLASS-01", "critical",
     "sterility, data-integrity, or patient-safety impact",
     lambda t, d: any(k in (t + " " + d).lower()
                      for k in ("steril", "data integrity", "patient safety",
                                "adulterat", "contaminat"))),
    ("CLASS-02", "critical",
     "repeat of a previously classified critical root cause",
     lambda t, d: False),  # applied by classify_repeat, not text
    ("CLASS-03", "major",
     "batch rejection risk, validation gap, or specification failure",
     lambda t, d: any(k in (t + " " + d).lower()
                      for k in ("validation gap", "out of specification",
                                "oos", "rejection", "residue", "excursion"))),
    ("CLASS-04", "major",
     "repeat occurrence of the same root cause",
     lambda t, d: False),  # applied by classify_repeat, not text
    ("CLASS-05", "minor",
     "documentation-only, no product impact",
     lambda t, d: any(k in (t + " " + d).lower()
                      for k in ("logbook", "typo", "font", "documentation",
                                "correction", "readability"))),
]


@dataclass
class Classification:
    dev_class: str
    rule_id: str
    rule_text: str
    evidence: str = ""


def classify(title: str, description: str) -> Classification:
    """Classify a deviation from its title + description text."""
    for rule_id, dev_class, rule_text, match in _RULES:
        if match(title, description):
            return Classification(dev_class, rule_id, rule_text,
                                  evidence=(title + " / " + description)[:120])
    # default: major — an unclassifiable deviation must not be minimized
    return Classification("major", "CLASS-00",
                          "default: unclassifiable deviations are treated as major",
                          evidence=(title + " / " + description)[:120])


def classify_repeat(title: str, description: str, prior_classes: list[str]) -> Classification:
    """Escalate repeats: a repeat of a critical root cause is critical (CLASS-02),
    a repeat of anything else is at least major (CLASS-04)."""
    if "critical" in prior_classes:
        return Classification("critical", "CLASS-02",
                              "repeat of a previously classified critical root cause")
    if prior_classes:
        return Classification("major", "CLASS-04",
                              "repeat occurrence of the same root cause")
    return classify(title, description)
