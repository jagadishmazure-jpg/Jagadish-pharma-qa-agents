"""PII scrubber: redacts email/phone/SSN/card/account patterns before storage.

Free-text feedback is scrubbed BEFORE it reaches the audit log — the lesson
from the sibling repos, where unscrubbed correction text was stored.
"""

from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[EMAIL]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # Includes "(555) 123-4567" and "+1 (555) 123-4567"; anchored so it never
    # matches inside batch IDs, dates or longer numbers.
    (re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b"), "[CARD]"),
    (re.compile(r"\b(?:acct|account)[\s#:]*\d{4,}\b", re.IGNORECASE), "[ACCOUNT]"),
]


def scrub(text: str) -> tuple[str, int]:
    """Return (scrubbed_text, redaction_count)."""
    count = 0
    for pattern, placeholder in _PATTERNS:
        text, n = pattern.subn(placeholder, text)
        count += n
    return text, count
