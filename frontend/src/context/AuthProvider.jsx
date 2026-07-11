import { useCallback, useEffect, useMemo, useState } from 'react';
import * as authService from '../services/authService';
import { clearToken, getToken } from '../utils/token';
import { AuthContext } from './authContext';

async function fetchCurrentUser() {
  if (!getToken()) {
    return null;
  }

  try {
    return await authService.getCurrentUser();
  } catch {
    clearToken();
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(function loadUser() {
    fetchCurrentUser().then((currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback(function login(email, password) {
    return authService.login(email, password).then(() => authService.getCurrentUser()).then(setUser);
  }, []);

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
