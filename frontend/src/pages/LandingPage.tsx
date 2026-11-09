import { Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { BackgroundPaths } from "@/components/ui/background-paths";
import { Button } from "@/components/ui/button";
import { FeaturesSection } from "@/components/landing/FeaturesSection";
import { HowItWorksSection } from "@/components/landing/HowItWorksSection";
import { LandingNavbar } from "@/components/landing/LandingNavbar";

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function LandingPage() {
  const { isAuthenticated } = useAuth();

  const primaryHref = isAuthenticated ? "/dashboard" : "/register";
  const primaryLabel = isAuthenticated ? "Go to Dashboard" : "Get Started";

  return (
    <div className="landing-root min-h-screen overflow-x-hidden">
      <LandingNavbar />

      <BackgroundPaths
        title={"Understand your documents.\nTrace every AI decision."}
        description="Extract, classify, and summarize documents while investigating the AI pipeline behind every result."
      >
        <Button
          asChild
          size="lg"
          className="w-full sm:w-auto rounded-xl px-8 text-white hover:text-white focus-visible:text-white active:text-white visited:text-white"
        >
          <Link to={primaryHref}>{primaryLabel}</Link>
        </Button>
        <Button
          type="button"
          variant="outline"
          size="lg"
          className="w-full sm:w-auto rounded-xl border-[#D6DEDA] bg-white text-[#203536] hover:bg-[#F7F8F6]"
          onClick={() => scrollToId("features")}
        >
          Explore Features
        </Button>
      </BackgroundPaths>

      <HowItWorksSection />
      <FeaturesSection />

      <section
        className="border-t border-[#D6DEDA] bg-white py-16 md:py-20"
        aria-labelledby="why-heading"
      >
        <div className="mx-auto max-w-3xl px-4 md:px-6 text-center">
          <h2
            id="why-heading"
            className="text-3xl md:text-4xl font-bold text-[#203536] tracking-tight"
          >
            Why Failure Forensics
          </h2>
          <p className="mt-6 text-[#687A78] text-lg leading-relaxed text-left sm:text-center">
            Most AI tools hand you a result and hide the steps in between. When something
            breaks, you are left searching logs or re-running blindly. Failure Forensics
            keeps document processing and pipeline observability in one place—so you can
            trace execution, review span-level evidence, and investigate failures with
            structured analysis and human feedback. It will not magically fix every issue,
            but it makes failures easier to understand and iterate on.
          </p>
        </div>
      </section>

      <section className="border-t border-[#D6DEDA] bg-[#173E42] py-16 md:py-20">
        <div className="mx-auto max-w-3xl px-4 md:px-6 text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-white tracking-tight">
            Make AI failures easier to understand.
          </h2>
          <p className="mt-4 text-white/75 text-lg">
            Start with a document upload, follow the trace when things go wrong, and improve
            with evaluations and analytics.
          </p>
          <Button asChild size="lg" className="mt-8 rounded-xl px-10">
            <Link to={isAuthenticated ? "/dashboard" : "/register"}>
              {isAuthenticated ? "Go to Dashboard" : "Start Investigating"}
            </Link>
          </Button>
        </div>
      </section>

      <footer className="border-t border-[#D6DEDA] bg-[#F7F8F6] py-8 text-center text-sm text-[#687A78]">
        Failure Forensics — document processing with traceable AI pipelines.
      </footer>
    </div>
  );
}
