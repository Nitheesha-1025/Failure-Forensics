import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";

function pathDuration(id: number): number {
  return 20 + (id % 11);
}

function FloatingPaths({ position }: { position: number }) {
  const reduceMotion = useReducedMotion();
  const paths = Array.from({ length: 36 }, (_, i) => ({
    id: i,
    d: `M-${380 - i * 5 * position} -${189 + i * 6}C-${
      380 - i * 5 * position
    } -${189 + i * 6} -${312 - i * 5 * position} ${216 - i * 6} ${
      152 - i * 5 * position
    } ${343 - i * 6}C${616 - i * 5 * position} ${470 - i * 6} ${
      684 - i * 5 * position
    } ${875 - i * 6} ${684 - i * 5 * position} ${875 - i * 6}`,
    width: 0.5 + i * 0.03,
  }));

  return (
    <div className="absolute inset-0 pointer-events-none" aria-hidden>
      <svg
        className="w-full h-full text-[#173E42]"
        viewBox="0 0 696 316"
        fill="none"
      >
        <title>Background paths</title>
        {paths.map((path) => (
          <motion.path
            key={path.id}
            d={path.d}
            stroke="currentColor"
            strokeWidth={path.width}
            strokeOpacity={0.08 + path.id * 0.02}
            initial={reduceMotion ? false : { pathLength: 0.3, opacity: 0.5 }}
            animate={
              reduceMotion
                ? { pathLength: 1, opacity: 0.35 }
                : {
                    pathLength: 1,
                    opacity: [0.25, 0.45, 0.25],
                    pathOffset: [0, 1, 0],
                  }
            }
            transition={
              reduceMotion
                ? { duration: 0 }
                : {
                    duration: pathDuration(path.id),
                    repeat: Number.POSITIVE_INFINITY,
                    ease: "linear",
                  }
            }
          />
        ))}
      </svg>
    </div>
  );
}

export interface BackgroundPathsProps {
  title?: string;
  description?: string;
  children?: ReactNode;
  className?: string;
}

export function BackgroundPaths({
  title = "Understand your documents Trace every AI decision",
  description,
  children,
  className,
}: BackgroundPathsProps) {
  const reduceMotion = useReducedMotion();
  const lines = title.split("\n").map((line) => line.trim()).filter(Boolean);

  return (
    <div
      className={cn(
        "relative min-h-[min(92vh,52rem)] w-full flex items-center justify-center overflow-hidden bg-[#F7F8F6]",
        className,
      )}
    >
      <div className="absolute inset-0">
        <FloatingPaths position={1} />
        <FloatingPaths position={-1} />
      </div>

      <div className="relative z-10 container mx-auto px-4 md:px-6 text-center max-w-5xl">
        <motion.div
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: reduceMotion ? 0 : 1.2 }}
          className="mx-auto"
        >
          <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold mb-6 tracking-tight text-[#203536] leading-[1.08]">
            {lines.map((line, lineIndex) => {
              const words = line.split(" ").filter(Boolean);
              let wordOffset = lines
                .slice(0, lineIndex)
                .reduce((acc, l) => acc + l.split(" ").filter(Boolean).length, 0);
              return (
                <span key={lineIndex} className="block">
                  {words.map((word, wordIndex) => {
                    const globalWordIndex = wordOffset + wordIndex;
                    return (
                      <span
                        key={wordIndex}
                        className="inline-block mr-[0.35em] last:mr-0"
                      >
                        {word.split("").map((letter, letterIndex) => (
                          <motion.span
                            key={`${globalWordIndex}-${letterIndex}`}
                            initial={reduceMotion ? false : { y: 40, opacity: 0 }}
                            animate={{ y: 0, opacity: 1 }}
                            transition={
                              reduceMotion
                                ? { duration: 0 }
                                : {
                                    delay: globalWordIndex * 0.08 + letterIndex * 0.025,
                                    type: "spring",
                                    stiffness: 150,
                                    damping: 25,
                                  }
                            }
                            className="inline-block"
                          >
                            {letter}
                          </motion.span>
                        ))}
                      </span>
                    );
                  })}
                </span>
              );
            })}
          </h1>

          {description ? (
            <p className="text-base sm:text-lg md:text-xl text-[#687A78] max-w-2xl mx-auto mb-10 leading-relaxed">
              {description}
            </p>
          ) : null}

          {children ? (
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
              {children}
            </div>
          ) : null}
        </motion.div>
      </div>
    </div>
  );
}
