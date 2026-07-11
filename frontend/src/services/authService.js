import { request, API_URL } from './api';
import { setToken } from '../utils/token';

export async function register(email, password) {
  return request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email, password) {
  const body = new URLSearchParams({
    username: email,
    password,
  });

  const response = await fetch(`${API_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });

  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.detail || 'Login failed');
  }

  const data = await response.json();
  setToken(data.access_token);
  return data;
}

export async function getCurrentUser() {
  return request('/api/auth/me');
}
