// App shell: auth context + URL routes
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import HelpChat from './components/HelpChat';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import RequireRole from './components/RequireRole';
import { AuthProvider } from './context/AuthProvider';
import AdminPage from './pages/AdminPage';
import IncidentDetailPage from './pages/IncidentDetailPage';
import IncidentsPage from './pages/IncidentsPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import TasksPage from './pages/TasksPage';

export default function App() {
  return (
    // AuthProvider shares login state (user, login, logout) with the whole tree
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public pages */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Private pages — ProtectedRoute redirects to /login if not authenticated */}
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<TasksPage />} /> {/* "/" */}
              <Route path="incidents" element={<IncidentsPage />} />
              <Route path="incidents/:id" element={<IncidentDetailPage />} />
              <Route path="admin" element={<RequireRole role="admin"><AdminPage /></RequireRole>} />
            </Route>
          </Route>

          {/* Unknown URL → home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        {/* Round chat button for questions about this repo (shown only when the assistant container is up) */}
        <HelpChat />
      </BrowserRouter>
    </AuthProvider>
  );
}
