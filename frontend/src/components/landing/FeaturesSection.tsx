import { motion, useReducedMotion } from "framer-motion";

import {
  IconAnalytics,
  IconDocuments,
  IconEvaluations,
} from "@/components/icons/Icons";
import { cn } from "@/lib/utils";

function IconTrace(props: { className?: string; size?: number }) {
  const s = props.size ?? 22;
  return (
    <svg
      className={props.className}
      width={s}
      height={s}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      aria-hidden
    >
      <path d="M4 19h16" />
      <path d="M7 16V8" />
      <path d="M12 16V5" />
      <path d="M17 16v-6" />
    </svg>
  );
}

function IconFeedback(props: { className?: string; size?: number }) {
  const s = props.size ?? 22;
  return (
    <svg
      className={props.className}
      width={s}
      height={s}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      aria-hidden
    >
      <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />
    </svg>
  );
}

function IconSearch(props: { className?: string; size?: number }) {
  const s = props.size ?? 22;
  return (
    <svg
      className={props.className}
      width={s}
      height={s}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      aria-hidden
    >
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3-3" />
    </svg>
  );
}

const features = [
  {
    title: "AI document processing",
    body: "Upload files, run extraction, classification, and summarization in one workspace tied to your account.",
    Icon: IconDocuments,
  },
  {
    title: "Execution tracing",
    body: "Inspect pipeline runs span-by-span with status, duration, and linked details when you need to debug.",
    Icon: IconTrace,
  },
  {
    title: "Root-cause analysis",
    body: "Investigate failed runs with structured failure analysis and evidence from the trace—not guesswork.",
    Icon: IconSearch,
  },
  {
    title: "Evaluations & regression testing",
    body: "Track evaluation runs over time and compare outcomes as you change prompts or pipeline steps.",
    Icon: IconEvaluations,
  },
  {
    title: "Human feedback",
    body: "Capture reviewer notes on analyses and spans so teams can improve reliability with real context.",
    Icon: IconFeedback,
  },
  {
    title: "Analytics",
    body: "See aggregate run and document metrics to spot patterns in failures and processing volume.",
    Icon: IconAnalytics,
  },
] as const;

export function FeaturesSection() {
  const reduceMotion = useReducedMotion();

  return (
    <section
      id="features"
      className="scroll-mt-20 py-16 md:py-24 bg-[#F7F8F6]"
      aria-labelledby="features-heading"
    >
      <div className="mx-auto max-w-6xl px-4 md:px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-wide text-[#397B78]">
            Core capabilities
          </p>
          <h2
            id="features-heading"
            className="mt-2 text-3xl md:text-4xl font-bold text-[#203536] tracking-tight"
          >
            Built for documents and the pipeline behind them
          </h2>
          <p className="mt-4 text-[#687A78] text-lg leading-relaxed">
            Failure Forensics is not just a summarizer—it helps you understand outputs and
            the AI execution path that produced them.
          </p>
        </div>

        <ul className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, index) => (
            <motion.li
              key={feature.title}
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.4, delay: reduceMotion ? 0 : index * 0.05 }}
              className={cn(
                "rounded-xl border border-[#D6DEDA] bg-white p-6",
                "transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md hover:border-[#397B78]/30",
              )}
            >
              <div className="text-[#397B78]">
                <feature.Icon size={22} />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-[#203536]">{feature.title}</h3>
              <p className="mt-2 text-sm text-[#687A78] leading-relaxed">{feature.body}</p>
            </motion.li>
          ))}
        </ul>
      </div>
    </section>
  );
}
