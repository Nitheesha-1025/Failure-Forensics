import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";

export function PublicHeader() {
  const { isAuthenticated } = useAuth();

  return (
    <header className="public-header">
      <div className="public-header-inner">
        <Link to="/" className="brand">
          <span className="sidebar-mark" aria-hidden />
          Failure Forensics
        </Link>
        <nav className="public-nav" aria-label="Public">
          {isAuthenticated ? (
            <Link to="/dashboard" className="btn btn-primary btn-sm">
              Open workspace
            </Link>
          ) : (
            <>
              <NavLink to="/login" className="nav-link">
                Sign in
              </NavLink>
              <Link to="/register" className="btn btn-primary btn-sm">
                Get started
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
