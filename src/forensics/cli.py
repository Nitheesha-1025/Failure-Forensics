"""CLI: run a single doc through the pipeline, serve the API, list traces."""

from __future__ import annotations

import asyncio
import sys

import click
import uvicorn

from .api.app import AppState, create_app
from .config import load_settings
from .llm_config import LLMConfigurationError, build_llm_client, resolve_llm_settings
from .logging import configure as configure_logging
from .pipeline import Pipeline, run_pipeline
from .storage import TraceStore

_DEFAULT_LABELS = [
    "billing",
    "bug_report",
    "feature_request",
    "general_inquiry",
]


@click.group()
def main() -> None:
    """failure-forensics CLI."""


@main.command("run")
@click.option("--document-id", required=True)
@click.option("--text", required=True, help="Raw document text")
def run_cmd(document_id: str, text: str) -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    try:
        llm = resolve_llm_settings(settings)
    except LLMConfigurationError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    async def _run() -> int:
        client = build_llm_client(llm, settings=settings)
        try:
            pipeline = Pipeline(
                client=client,
                extraction_model=llm.extraction_model,
                classification_model=llm.classification_model,
                summarization_model=llm.summarization_model,
                labels=_DEFAULT_LABELS,
            )
            store = TraceStore(settings.db_path, settings.traces_dir)
            final, trace = await run_pipeline(
                pipeline, document_id=document_id, raw_text=text
            )
            store.save_trace(trace)
            click.echo(f"trace_id={trace.trace_id} status={trace.status.value}")
            click.echo(f"spans={len(trace.spans)} duration_ms={trace.duration_ms}")
            if final is not None:
                click.echo(f"summary: {final.summary}")
            else:
                click.echo("pipeline failed before producing a summary", err=True)
            return 0
        finally:
            await client.aclose()

    sys.exit(asyncio.run(_run()))


@main.command("serve")
def serve_cmd() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    try:
        llm = resolve_llm_settings(settings)
    except LLMConfigurationError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    client = build_llm_client(llm, settings=settings)
    pipeline = Pipeline(
        client=client,
        extraction_model=llm.extraction_model,
        classification_model=llm.classification_model,
        summarization_model=llm.summarization_model,
        labels=_DEFAULT_LABELS,
    )
    store = TraceStore(settings.db_path, settings.traces_dir)
    state = AppState(pipeline=pipeline, store=store, judge_model=llm.judge_model)
    app = create_app(state)
    uvicorn.run(app, host=settings.api_host, port=settings.api_port,
                log_level=settings.log_level.lower())


@main.command("traces")
@click.option("--limit", default=20)
@click.option("--flagged-only", is_flag=True)
def traces_cmd(limit: int, flagged_only: bool) -> None:
    settings = load_settings()
    store = TraceStore(settings.db_path, settings.traces_dir)
    rows = store.list_traces(limit=limit, only_flagged=flagged_only)
    if not rows:
        click.echo("(no traces)")
        return
    for r in rows:
        flag_marker = " 🚩" if r["flagged"] else ""
        click.echo(
            f"{r['started_at']}  {r['trace_id']}  "
            f"status={r['status']}  spans={r['n_spans']}  "
            f"{r['duration_ms']}ms{flag_marker}"
        )


if __name__ == "__main__":  # pragma: no cover
    main()
