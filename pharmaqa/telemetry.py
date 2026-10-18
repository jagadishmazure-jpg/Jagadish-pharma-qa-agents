"""Synthetic pharma QA telemetry on SQLite.

Fictional site "Newbridge" of the invented manufacturer Meridian Therapeutics.
All data is synthetic and deterministic (seeded) so every run matches the
README figures and the tests.
"""

from __future__ import annotations

import sqlite3

SEED = 42

SCHEMA = """
CREATE TABLE batches (
    batch_id   TEXT PRIMARY KEY,
    product    TEXT NOT NULL,
    site       TEXT NOT NULL,
    status     TEXT NOT NULL,   -- manufacturing | qa_review | released | rejected | on_hold
    mfg_date   TEXT NOT NULL
);
CREATE TABLE deviations (
    dev_id      TEXT PRIMARY KEY,
    batch_id    TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    dev_class   TEXT NOT NULL,   -- critical | major | minor
    status      TEXT NOT NULL,   -- open | investigating | closed
    root_cause  TEXT NOT NULL,
    opened_date TEXT NOT NULL,
    due_date    TEXT NOT NULL,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
);
CREATE TABLE capas (
    capa_id    TEXT PRIMARY KEY,
    dev_id     TEXT NOT NULL,
    title      TEXT NOT NULL,
    status     TEXT NOT NULL,     -- open | in_progress | overdue | closed
    owner      TEXT NOT NULL,
    due_date   TEXT NOT NULL,
    FOREIGN KEY (dev_id) REFERENCES deviations(dev_id)
);
CREATE TABLE signoffs (
    signoff_id TEXT PRIMARY KEY,
    batch_id   TEXT NOT NULL,
    role       TEXT NOT NULL,     -- qa_reviewer | qa_manager | qualified_person
    approver   TEXT NOT NULL,
    decision   TEXT NOT NULL,     -- pending | approved | rejected
    criteria   TEXT NOT NULL,
    decided_on TEXT,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
);
CREATE TABLE audit_findings (
    finding_id TEXT PRIMARY KEY,
    area       TEXT NOT NULL,
    severity   TEXT NOT NULL,     -- critical | major | minor
    status     TEXT NOT NULL,     -- open | closed
    due_date   TEXT NOT NULL
);
"""


def build_db(path: str = ":memory:") -> sqlite3.Connection:
    """Create and seed the synthetic QA database. Deterministic."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    batches = [
        # batch_id, product, site, status, mfg_date
        ("BATCH-2026-0142", "Cardiorex 50mg", "Newbridge", "on_hold", "2026-09-28"),
        ("BATCH-2026-0143", "Cardiorex 50mg", "Newbridge", "qa_review", "2026-10-02"),
        ("BATCH-2026-0144", "Neurovia 10mg", "Newbridge", "qa_review", "2026-10-05"),
        ("BATCH-2026-0145", "Neurovia 10mg", "Newbridge", "released", "2026-09-15"),
        ("BATCH-2026-0146", "Dermaclear cream", "Newbridge", "manufacturing", "2026-10-12"),
        ("BATCH-2026-0147", "Cardiorex 50mg", "Newbridge", "rejected", "2026-08-30"),
    ]
    conn.executemany("INSERT INTO batches VALUES (?,?,?,?,?)", batches)

    deviations = [
        # dev_id, batch_id, title, description, class, status, root_cause, opened, due
        ("DEV-CRIT-007", "BATCH-2026-0142", "Sterility test failure",
         "Environmental monitoring excursion in fill room B; sterility impact cannot be ruled out",
         "critical", "open", "HVAC filter integrity lapse", "2026-10-03", "2026-10-17"),
        ("DEV-MAJ-021", "BATCH-2026-0143", "Cleaning validation gap",
         "Residue above limit on shared equipment train after product changeover",
         "major", "investigating", "cleaning validation gap", "2026-10-06", "2026-10-20"),
        ("DEV-MAJ-022", "BATCH-2026-0144", "Cleaning validation gap",
         "Same residue pattern on second train; repeat of DEV-MAJ-021 root cause",
         "major", "open", "cleaning validation gap", "2026-10-09", "2026-10-23"),
        ("DEV-MAJ-023", "BATCH-2026-0142", "Cleaning validation gap",
         "Historical review finds the same gap on a third train",
         "major", "open", "cleaning validation gap", "2026-10-10", "2026-10-24"),
        ("DEV-MIN-031", "BATCH-2026-0144", "Logbook entry correction",
         "Operator corrected a time entry; no product impact",
         "minor", "closed", "documentation error", "2026-10-07", "2026-10-14"),
        ("DEV-MIN-032", "BATCH-2026-0143", "Label font deviation",
         "Secondary label font differs from artwork; readability unaffected",
         "minor", "open", "artwork version mismatch", "2026-10-11", "2026-10-25"),
    ]
    conn.executemany("INSERT INTO deviations VALUES (?,?,?,?,?,?,?,?,?)", deviations)

    capas = [
        # capa_id, dev_id, title, status, owner, due
        ("CAPA-009", "DEV-MAJ-021", "Revalidate cleaning procedure CP-114",
         "overdue", "Q. Alvarez", "2026-10-12"),
        ("CAPA-010", "DEV-CRIT-007", "Replace HVAC filters + requalify fill room B",
         "in_progress", "R. Okafor", "2026-10-28"),
        ("CAPA-011", "DEV-MAJ-022", "Extend revalidation to all shared trains",
         "open", "Q. Alvarez", "2026-11-05"),
        ("CAPA-012", "DEV-MIN-031", "Retrain operators on logbook corrections",
         "closed", "S. Iyer", "2026-10-10"),
    ]
    conn.executemany("INSERT INTO capas VALUES (?,?,?,?,?,?)", capas)

    signoffs = [
        # signoff_id, batch_id, role, approver, decision, criteria, decided_on
        ("SO-142-1", "BATCH-2026-0142", "qa_reviewer", "J. Mensah", "rejected",
         "no open critical deviations", "2026-10-04"),
        ("SO-142-2", "BATCH-2026-0142", "qa_manager", "", "pending",
         "CAPAs for majors on track", None),
        ("SO-142-3", "BATCH-2026-0142", "qualified_person", "", "pending",
         "batch record complete, no open deviations", None),
        ("SO-143-1", "BATCH-2026-0143", "qa_reviewer", "J. Mensah", "approved",
         "no open critical deviations", "2026-10-08"),
        ("SO-143-2", "BATCH-2026-0143", "qa_manager", "", "pending",
         "CAPAs for majors on track", None),
        ("SO-143-3", "BATCH-2026-0143", "qualified_person", "", "pending",
         "batch record complete, no open deviations", None),
        ("SO-145-1", "BATCH-2026-0145", "qa_reviewer", "J. Mensah", "approved",
         "no open critical deviations", "2026-09-20"),
        ("SO-145-2", "BATCH-2026-0145", "qa_manager", "L. Fontaine", "approved",
         "CAPAs for majors on track", "2026-09-21"),
        ("SO-145-3", "BATCH-2026-0145", "qualified_person", "D. Reyes", "approved",
         "batch record complete, no open deviations", "2026-09-22"),
    ]
    conn.executemany("INSERT INTO signoffs VALUES (?,?,?,?,?,?,?)", signoffs)

    findings = [
        # finding_id, area, severity, status, due
        ("AF-101", "data integrity", "major", "open", "2026-10-30"),
        ("AF-102", "sterile operations", "critical", "open", "2026-10-18"),
        ("AF-103", "training records", "minor", "closed", "2026-09-30"),
    ]
    conn.executemany("INSERT INTO audit_findings VALUES (?,?,?,?,?)", findings)

    conn.commit()
    return conn


# Deterministic anchors used by tests and README figures.
ANCHORS = {
    "blocked_batch": "BATCH-2026-0142",      # on_hold: open critical DEV-CRIT-007
    "repeat_root_cause": "cleaning validation gap",  # 3 deviations
    "overdue_capa": "CAPA-009",
    "critical_deviation": "DEV-CRIT-007",
}
