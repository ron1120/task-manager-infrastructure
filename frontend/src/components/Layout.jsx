// Shared chrome for logged-in pages (header + logout)
import { Link, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Task Manager</h1>
          <p className="muted">Signed in as {user?.email}</p>
        </div>
        <div className="header-actions">
          <Link to="/" className="button secondary">
            Tasks
          </Link>
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
