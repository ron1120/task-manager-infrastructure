// Convenience hook — pages/components call useAuth() instead of useContext directly
import { useContext } from 'react';
import { AuthContext } from '../context/authContext';

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context; // { user, loading, login, register, logout, isAuthenticated }
}
