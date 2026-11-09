"""Streamlit visual trace explorer.

Lazy-imports streamlit so this module is importable in environments where
the optional `[ui]` extra isn't installed.

Run with:
    streamlit run -m forensics.explorer
or
    python -m forensics.explorer
(streamlit will be auto-detected from the env).
"""

from __future__ import annotations

from pathlib import Path

from .config import load_settings
from .storage import TraceStore


def render() -> None:  # pragma: no cover — streamlit-only path
    import streamlit as st

    settings = load_settings()
    store = TraceStore(Path(settings.db_path), Path(settings.traces_dir))

    st.set_page_config(page_title="failure-forensics", layout="wide")
    st.title("failure-forensics — trace explorer")

    only_flagged = st.sidebar.checkbox("Only flagged", value=False)
    rows = store.list_traces(limit=200, only_flagged=only_flagged)
    if not rows:
        st.info("No traces yet. Run the pipeline first.")
        return

    options = {f"{r['started_at']}  {r['trace_id']}  ({r['status']})": r["trace_id"] for r in rows}
    chosen = st.sidebar.selectbox("Trace", list(options.keys()))
    trace_id = options[chosen]

    trace = store.get_trace(str(trace_id))
    if trace is None:
        st.error("Trace payload missing on disk.")
        return

    analysis = store.get_analysis(str(trace_id))
    rc_id = analysis.root_cause_span_id if analysis else None

    cols = st.columns([2, 3])
    with cols[0]:
        st.subheader(f"Spans ({len(trace.spans)})")
        for span in trace.spans:
            tag = "🛑 ROOT" if span.span_id == rc_id else ""
            color = "red" if span.status.value == "error" else (
                "orange" if (span.confidence or 1.0) < 0.6 else "green"
            )
            st.markdown(
                f"- **{span.name}** :{color}[{span.duration_ms}ms]  "
                f"conf={span.confidence}  {tag}"
            )
    with cols[1]:
        st.subheader("Detail")
        for span in trace.spans:
            with st.expander(f"{span.name} ({span.duration_ms}ms)"):
                st.json({"input": span.input, "output": span.output})
                if span.error:
                    st.error(span.error)

    if analysis is not None:
        st.subheader("Root cause analysis")
        st.write(analysis.root_cause_explanation)


if __name__ == "__main__":  # pragma: no cover
    render()
