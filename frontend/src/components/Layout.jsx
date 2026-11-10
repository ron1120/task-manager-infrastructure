// Shared chrome for logged-in pages (header + logout)
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { hasRole } from '../utils/ops';

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Task Manager</h1>
          <p className="muted">Signed in as {user?.email} ({user?.role})</p>
        </div>
        <div className="header-actions">
          <NavLink to="/" end className="button secondary">
            Tasks
          </NavLink>
          <NavLink to="/incidents" className="button secondary">
            Incidents
          </NavLink>
          {hasRole(user, 'admin') && (
            <NavLink to="/admin" className="button secondary">
              Admin
            </NavLink>
          )}
          <button type="button" className="button secondary" onClick={logout}>
            Logout
          </button>
        </div>
      </header>
      <main className="app-main">
        {/* Nested route content renders here (e.g. TasksPage) */}
        <Outlet />
      </main>
    </div>
  );
}
