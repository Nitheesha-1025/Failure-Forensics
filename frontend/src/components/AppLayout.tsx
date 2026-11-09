import { Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { PublicHeader } from "./layout/PublicHeader";
import { Sidebar } from "./layout/Sidebar";
import { TopBar } from "./layout/TopBar";

const PUBLIC_STANDALONE = new Set(["/login", "/register"]);

export function AppLayout() {
  const { isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  const workspace =
    isAuthenticated && !PUBLIC_STANDALONE.has(pathname);

  if (pathname === "/") {
    return (
      <div className="app-shell app-shell--landing">
        <Outlet />
      </div>
    );
  }

  if (workspace) {
    return (
      <div className="app-shell app-shell--workspace">
        <Sidebar />
        <div className="app-main-column">
          <TopBar />
          <main className="main-content" id="main-content">
            <Outlet />
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell app-shell--public">
      <PublicHeader />
      <main className="main-content main-content--public" id="main-content">
        <Outlet />
      </main>
    </div>
  );
}
