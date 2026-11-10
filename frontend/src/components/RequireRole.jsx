// Route guard: renders its children only for users with at least the given role
import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { hasRole } from '../utils/ops';

export default function RequireRole({ role, children }) {
  const { user } = useAuth();
  return hasRole(user, role) ? children : <Navigate to="/incidents" replace />;
}
