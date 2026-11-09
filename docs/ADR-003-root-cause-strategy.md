# ADR-003: "First quality cliff" beats "lowest-scoring span" or "purely backward from final"

**Status:** Accepted

## Context

The spec says "backward trace analyzer: LLM-as-judge per step; first significant quality drop = root cause." Three reasonable implementations:

1. **Lowest-scoring span overall.** Pick `argmin(quality)`.
2. **Purely backward from the final output.** Walk spans in reverse, stopping at the first one whose output looks bad.
3. **Forward walk, stop at first quality cliff.** Critique every span; walk in execution order; the root cause is the first span where quality drops below threshold while the previous span was above it.

## Decision

Option 3, with two short-circuits:

- A step that **raised** is the root cause immediately (no judge call needed).
- A span that the judge marks `is_root_cause_candidate=true` wins over a downstream cliff.

## Consequences

**Why this is the right choice:**

- **Cascading failures are correctly attributed.** When extraction fails to find the right fields, classification gets garbage and scores low. Naively, both look "broken" — but only extraction is the cause; classification is doing its best with bad input. The forward-walk picks extraction (the *first* span below threshold).
- **Low-quality but correct steps don't get blamed.** A summarization step that scores 0.55 because the document is genuinely ambiguous shouldn't be flagged when an upstream step scored 0.30. Lowest-overall would flag the summarization; we want the upstream cause.
- **The final-output-backward variant is fragile.** If the final summary "looks fine" by accident even though extraction was wrong, a backward walk stops too early. Forward-walking with judges per span makes the trace's internal disagreement visible.
- **The judge can flag a single bad step explicitly** even when its output happens to score well. The `is_root_cause_candidate` field is the judge's escape hatch for "this output is plausible-looking but actually wrong on its own."

**Trade-offs:**

- The judge runs on **every** span, not just the suspicious ones. That's N extra LLM calls per analysis. We bound this with a semaphore (default concurrency 4) and accept the cost — the alternative is much harder to debug.
- The "min_quality" threshold is a knob. We default to 0.6 and document it. Different teams will tune it; the analyzer surfaces the per-span scores so a wrong threshold is visible at a glance.
- A pipeline that's universally mediocre (every span at 0.5) blames the first span via the fallback. That's defensible: when nothing is clearly broken, the user should look at the chain end-to-end, and the report's `root_cause_explanation` says exactly that.

## Alternatives considered

- **Two-LLM strategy** (one critic per span + a meta-critic for the chain). More accurate, much more expensive. Worth it at scale; not for a v0.
- **Confidence-only routing** (flag whichever span has the lowest in-pipeline `confidence` value). Cheaper than the judge; misses cases where the step happily emits high-confidence garbage.

## Revisit if

- We see frequent reports of the analyzer fingering the wrong span. Adding a meta-critic that takes the per-span `SpanCritique` list and returns a final verdict is a one-file extension.
- LLM-judge cost per analysis becomes a real budget concern. The first move is to skip the judge for spans whose own confidence is above ~0.95 (cheap shortcut), keeping the meta-strategy intact.
