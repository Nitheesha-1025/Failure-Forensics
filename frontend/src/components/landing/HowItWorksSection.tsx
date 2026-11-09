import { motion, useReducedMotion } from "framer-motion";

import {
  IconDocuments,
  IconEvaluations,
  IconUpload,
} from "@/components/icons/Icons";
import { cn } from "@/lib/utils";

const steps = [
  {
    n: 1,
    title: "Upload a document",
    body: "Add PDF, DOCX, TXT, or Markdown files to your workspace under your account.",
    Icon: IconUpload,
  },
  {
    n: 2,
    title: "Extract information",
    body: "The pipeline pulls structured fields and text from each document for downstream steps.",
    Icon: IconDocuments,
  },
  {
    n: 3,
    title: "Classify content",
    body: "Documents are labeled and routed so you can see how the AI interpreted each file.",
    Icon: IconEvaluations,
  },
  {
    n: 4,
    title: "Generate a summary",
    body: "Summaries and outputs are produced with a full execution trace you can open when something fails.",
    Icon: IconDocuments,
  },
] as const;

export function HowItWorksSection() {
  const reduceMotion = useReducedMotion();

  return (
    <section
      id="how-it-works"
      className="scroll-mt-20 border-t border-[#D6DEDA] bg-white py-16 md:py-24"
      aria-labelledby="how-it-works-heading"
    >
      <div className="mx-auto max-w-6xl px-4 md:px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-wide text-[#397B78]">
            How it works
          </p>
          <h2
            id="how-it-works-heading"
            className="mt-2 text-3xl md:text-4xl font-bold text-[#203536] tracking-tight"
          >
            From upload to traceable results
          </h2>
          <p className="mt-4 text-[#687A78] text-lg leading-relaxed">
            Run document processing as a multi-step pipeline. When a step fails, open the
            trace to see spans, timing, and evidence—not just the final error message.
          </p>
        </div>

        <ol className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, index) => (
            <motion.li
              key={step.n}
              initial={reduceMotion ? false : { opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.45, delay: reduceMotion ? 0 : index * 0.08 }}
              className={cn(
                "group relative rounded-xl border border-[#D6DEDA] bg-[#F7F8F6] p-6",
                "transition-shadow duration-300 hover:shadow-md hover:border-[#397B78]/35",
              )}
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#173E42] text-white text-sm font-bold">
                {step.n}
              </span>
              <div className="mt-4 text-[#397B78] group-hover:text-[#2E6663] transition-colors">
                <step.Icon size={22} className="inline-block" />
              </div>
              <h3 className="mt-3 text-lg font-semibold text-[#203536]">{step.title}</h3>
              <p className="mt-2 text-sm text-[#687A78] leading-relaxed">{step.body}</p>
            </motion.li>
          ))}
        </ol>
      </div>
    </section>
  );
}
