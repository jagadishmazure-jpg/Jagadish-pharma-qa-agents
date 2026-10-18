"""Thin Streamlit demo. Run:  pip install streamlit ; streamlit run demo/app.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    raise SystemExit("pip install streamlit, then: streamlit run demo/app.py")

from pharmaqa import demo_helpers as dh
from pharmaqa.audit import AuditLog
from pharmaqa.orchestrator import Orchestrator
from pharmaqa.sop_rag import SopRetriever, load_chunks
from pharmaqa.telemetry import build_db
from pharmaqa.views import create_views

st.set_page_config(page_title="Pharma QA Ops — agent demo", layout="wide")
st.title("Pharma QA deviation management — agent demo")
st.caption("Synthetic data · Meridian Therapeutics (fictional) · Newbridge site")

conn = build_db()
create_views(conn)
audit = AuditLog()
retriever = SopRetriever(load_chunks(Path(__file__).resolve().parents[1] / "docs" / "sops"))
orc = Orchestrator(conn, retriever, audit)

tab1, tab2, tab3 = st.tabs(["Release pipeline", "Ask", "Deviations & CAPAs"])

with tab1:
    for row in dh.release_pipeline(conn):
        with st.expander(f"{row['batch']} — {row['product']} ({row['status']})"):
            st.write("Released:", row["released"])
            for b in row["blocking"]:
                st.warning(b)

with tab2:
    q = st.text_input("Ask about deviations, batches, CAPAs, SOPs…",
                      "Which batches are blocked from release and why?")
    if st.button("Ask") and q:
        turn = orc.ask(q)
        for s in turn["steps"]:
            st.subheader(s["intent"])
            st.json(s["result"])

with tab3:
    st.subheader("Open deviations by class")
    st.table(dh.deviation_summary(conn))
    st.subheader("CAPA backlog")
    st.table(dh.capa_summary(conn))
