import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  IconAnalytics,
  IconChevronLeft,
  IconDashboard,
  IconDocuments,
  IconEvaluations,
  IconUpload,
} from "../icons/Icons";

const STORAGE_KEY = "ff-sidebar-collapsed";

const navItems = [
  { to: "/dashboard", label: "Dashboard", Icon: IconDashboard },
  { to: "/documents", label: "Documents", Icon: IconDocuments },
  { to: "/upload", label: "Upload", Icon: IconUpload },
  { to: "/evaluations", label: "Evaluations", Icon: IconEvaluations },
  { to: "/analytics", label: "Analytics", Icon: IconAnalytics },
] as const;

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      /* ignore */
    }
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  return (
    <aside
      className={`sidebar${collapsed ? " sidebar--collapsed" : ""}`}
      aria-label="Application"
    >
      <div className="sidebar-brand">
        <span className="sidebar-mark" aria-hidden />
        <div className="sidebar-brand-text">
          <span className="sidebar-title">Failure Forensics</span>
          <span className="sidebar-subtitle">Pipeline investigation</span>
        </div>
      </div>
      <nav className="sidebar-nav">
        {navItems.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `sidebar-link${isActive ? " sidebar-link--active" : ""}`
            }
            end={to === "/dashboard"}
            title={collapsed ? label : undefined}
          >
            <Icon size={16} />
            <span className="sidebar-link-label">{label}</span>
          </NavLink>
        ))}
      </nav>
      <button
        type="button"
        className="sidebar-collapse-btn"
        onClick={toggleCollapsed}
        aria-expanded={!collapsed}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <IconChevronLeft
          size={16}
          className={collapsed ? "sidebar-chevron sidebar-chevron--flipped" : "sidebar-chevron"}
        />
        <span className="sidebar-link-label">{collapsed ? "Expand" : "Collapse"}</span>
      </button>
    </aside>
  );
}
