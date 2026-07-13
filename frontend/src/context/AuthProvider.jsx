// Holds auth state for the whole app (who is logged in, login/logout helpers)
import { useCallback, useEffect, useMemo, useState } from 'react';
import * as authService from '../services/authService';
import { clearToken, getToken } from '../utils/token';
import { AuthContext } from './authContext';

async function fetchCurrentUser() {
  // No token → not logged in
  if (!getToken()) {
    return null;
  }

  try {
    return await authService.getCurrentUser(); // GET /api/auth/me
  } catch {
    // Token invalid/expired → clear it
    clearToken();
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On first load / refresh: restore session from localStorage token
  const loadUser = useCallback(function loadUser() {
    fetchCurrentUser().then((currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  // Login flow: get JWT → fetch /me → store user in React state
  const login = useCallback(function login(email, password) {
    return authService.login(email, password).then(() => authService.getCurrentUser()).then(setUser);
  }, []);

  // Register then auto-login
  const register = useCallback(function register(email, password) {
    return authService
      .register(email, password)
      .then(() => authService.login(email, password))
      .then(() => authService.getCurrentUser())
      .then(setUser);
  }, []);

  const logout = useCallback(function logout() {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, isAuthenticated: !!user }),
    [user, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
