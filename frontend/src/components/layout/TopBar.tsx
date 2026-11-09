import { useAuth } from "../../auth/AuthContext";
import { IconLogOut } from "../icons/Icons";

export function TopBar() {
  const { user, logout } = useAuth();

  return (
    <header className="topbar">
      <div className="topbar-start">
        <p className="topbar-context">Investigation workspace</p>
      </div>
      <div className="topbar-end">
        {user?.email ? (
          <span className="topbar-user" title={user.email}>
            {user.email}
          </span>
        ) : null}
        <button type="button" className="btn btn-ghost btn-sm topbar-logout" onClick={logout}>
          <IconLogOut size={16} />
          Logout
        </button>
      </div>
    </header>
  );
}
