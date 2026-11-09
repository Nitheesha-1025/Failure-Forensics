import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function LandingNavbar() {
  const { isAuthenticated } = useAuth();
  const [open, setOpen] = useState(false);

  const navLink =
    "text-sm font-medium text-[#687A78] hover:text-[#203536] transition-colors";

  return (
    <header className="sticky top-0 z-50 border-b border-[#D6DEDA] bg-[#F7F8F6]/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 md:px-6">
        <Link to="/" className="flex items-center gap-2 font-semibold text-[#203536]">
          <span className="h-6 w-1 rounded-sm bg-[#397B78]" aria-hidden />
          Failure Forensics
        </Link>

        <nav className="hidden md:flex items-center gap-6" aria-label="Primary">
          <a href="#features" className={navLink}>
            Features
          </a>
          <a href="#how-it-works" className={navLink}>
            How It Works
          </a>
          {isAuthenticated ? (
            <Button asChild size="sm">
              <Link to="/dashboard">Go to Dashboard</Link>
            </Button>
          ) : (
            <>
              <Link to="/login" className={navLink}>
                Login
              </Link>
              <Button
                asChild
                size="sm"
                className="text-white hover:text-white focus-visible:text-white active:text-white visited:text-white"
              >
                <Link to="/register">Get Started</Link>
              </Button>
            </>
          )}
        </nav>

        <button
          type="button"
          className="md:hidden rounded-md border border-[#D6DEDA] px-3 py-2 text-sm text-[#203536]"
          aria-expanded={open}
          aria-controls="landing-mobile-nav"
          onClick={() => setOpen((v) => !v)}
        >
          Menu
        </button>
      </div>

      <nav
        id="landing-mobile-nav"
        className={cn(
          "md:hidden border-t border-[#D6DEDA] bg-white px-4 py-3 flex flex-col gap-3",
          open ? "block" : "hidden",
        )}
        aria-label="Mobile"
      >
        <a href="#features" className={navLink} onClick={() => setOpen(false)}>
          Features
        </a>
        <a href="#how-it-works" className={navLink} onClick={() => setOpen(false)}>
          How It Works
        </a>
        {isAuthenticated ? (
          <Button asChild className="w-full">
            <Link to="/dashboard">Go to Dashboard</Link>
          </Button>
        ) : (
          <>
            <Link to="/login" className={navLink} onClick={() => setOpen(false)}>
              Login
            </Link>
            <Button asChild className="w-full">
              <Link to="/register">Get Started</Link>
            </Button>
          </>
        )}
      </nav>
    </header>
  );
}
