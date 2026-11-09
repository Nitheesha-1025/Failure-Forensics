"""End-to-end smoke test that hits a real OpenAI API key."""

from __future__ import annotations

import asyncio

from forensics.analyzer import analyze_trace
from forensics.config import load_settings
from forensics.llm_config import LLMConfigurationError, build_llm_client, resolve_llm_settings
from forensics.logging import configure
from forensics.pipeline import Pipeline, run_pipeline
from forensics.storage import TraceStore


async def main() -> None:
    configure("INFO")
    settings = load_settings()
    try:
        llm = resolve_llm_settings(settings)
    except LLMConfigurationError as exc:
        raise SystemExit(str(exc)) from exc

    client = build_llm_client(llm, settings=settings)
    pipeline = Pipeline(
        client=client,
        extraction_model=llm.extraction_model,
        classification_model=llm.classification_model,
        summarization_model=llm.summarization_model,
        labels=["billing", "bug_report", "feature_request", "general_inquiry"],
    )
    store = TraceStore(settings.db_path, settings.traces_dir)
    try:
        final, trace = await run_pipeline(
            pipeline,
            document_id="ex-1",
            raw_text="Hi, my card was charged $120 twice this month — please refund the duplicate.",
        )
        store.save_trace(trace)
        print(f"trace_id={trace.trace_id} status={trace.status.value}")
        if final is not None:
            print(f"summary: {final.summary}")

        analysis = await analyze_trace(trace, client=client, judge_model=llm.judge_model)
        store.save_analysis(analysis)
        print(f"root_cause: {analysis.root_cause_span_id}")
        print(f"explanation: {analysis.root_cause_explanation}")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
