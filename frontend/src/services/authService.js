// Frontend calls for /api/auth/...
import { request, API_URL } from './api';
import { setToken } from '../utils/token';

export async function register(email, password) {
  return request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email, password) {
  // OAuth2PasswordRequestForm expects form fields, not JSON
  const body = new URLSearchParams({
    username: email, // backend uses "username" field for the email
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
  setToken(data.access_token); // persist JWT for later API calls
  return data;
}

export async function getCurrentUser() {
  // Needs Bearer token — returns { id, email, created_at }
  return request('/api/auth/me');
}
