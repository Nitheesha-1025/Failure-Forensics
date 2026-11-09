# ADR-001: Decorator (`@traced`) instead of explicit context manager

**Status:** Accepted

## Context

The spec requires "decorator-based instrumentation, one-liner per step." Two ways to honor that:

1. A decorator that wraps the whole function and emits one span on each call.
2. A context manager (`with span("classification"):`) that the user wraps a body in.

## Decision

Decorator with optional `ctx: SpanContext` keyword-only injection. Steps that need to enrich the span declare `ctx` in their signature; steps that don't can ignore it.

## Consequences

**Why this is the right choice:**

- **One line per step.** That's the spec's stated standard. A context manager forces the body to be re-indented and the call sites to gain a `with` block.
- **Inputs and outputs are captured automatically.** The decorator inspects the function's `co_varnames`, drops `ctx`, and dumps the rest with Pydantic. With a context manager, the user is responsible for calling `span.set_input(...)` / `span.set_output(...)`, which means people forget and the trace becomes useless.
- **Errors are first-class.** A decorator's `try/except/finally` reliably converts exceptions to `StepStatus.ERROR` without forcing the caller to catch-and-rethrow. Context managers can do this too (`__exit__`), but the user still has to remember to wrap each call site.
- **Sync and async work the same.** The decorator detects `iscoroutinefunction` and dispatches; the user writes the same code shape either way.

**Trade-offs:**

- The decorator can't easily express "I want to record a partial sub-step inside this function." The escape hatch is `traced(name="...")` on a smaller helper function. We accept the loss of ad-hoc nested spans because the spec's pipelines are *step-shaped*, not arbitrary call trees.
- Argument introspection uses `co_varnames`, which means renamed positional args can confuse the input snapshot. We document this and provide `_input_snapshot()` as a single chokepoint to fix if it bites.
- We deliberately don't push spans to OpenTelemetry by default. The `@traced` decorator owns the source of truth (`SpanRecord`); users who want OTel can hand the recorder's spans to an exporter at the end of a run.

## Alternatives considered

- **OTel `Tracer.start_as_current_span` directly.** Tempting because it's standard. Rejected because OTel is optimized for observability dashboards (Jaeger, Tempo) — not for keeping rich Pydantic payloads attached to each span. Bridging back to OTel format is a one-screen exporter we can add when someone asks.
- **Both decorator AND context manager.** We may add the context-manager API later as a thin shim over `@traced`. Today, the decorator is enough.

## Revisit if

- A user asks for nested sub-steps inside one function call frequently enough that decorators feel unnatural.
- We start exporting to OTel collectors as the primary store, in which case the decorator becomes a thin adapter and the SQLite/JSON store becomes a cache.
