"""Print the domain differentiator on the seeded data (README block, CI-checked)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pharmaqa.classify import classify  # noqa: E402
from pharmaqa.demo_helpers import format_release  # noqa: E402
from pharmaqa.release import evaluate  # noqa: E402
from pharmaqa.telemetry import build_db  # noqa: E402
from pharmaqa.views import GatewayError, create_views, run_query  # noqa: E402

conn = build_db()
create_views(conn)
print("Batch-release sign-off chain (criterion AND recorded signature, in role order):")
for batch in ("BATCH-2026-0142", "BATCH-2026-0143", "BATCH-2026-0144", "BATCH-2026-0145",
              "BATCH-2026-0146", "BATCH-2026-0147"):
    print(format_release(evaluate(conn, batch)))
print()
print("Deviation classifier:")
for title, desc in (("Sterility test failure", "EM excursion in fill room B"),
                    ("Cleaning validation gap", "Residue above limit after changeover"),
                    ("Loose logbook binding", "documentation only, no product impact"),
                    ("Unlabelled tote found", "")):
    c = classify(title, desc)
    print(f"  {title!r}: {c.dev_class} ({c.rule_id})")
print()
try:
    run_query(conn, 'SELECT * FROM v_batch_pipeline, "signoffs"')
except GatewayError as exc:
    print(f"Gateway: {exc}")
