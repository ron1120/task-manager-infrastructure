// Shared HTTP helper for talking to the FastAPI backend
import { getToken } from '../utils/token';

// Backend base URL (from Vite env, or localhost for local dev)
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // Attach JWT on every request when logged in
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = 'Request failed';
    try {
      const data = await response.json();
      message = data.detail || message; // FastAPI puts errors in `detail`
    } catch {
      // ignore parse errors
    }
    throw new ApiError(message, response.status);
  }

  // DELETE endpoints often return 204 No Content
  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export { API_URL, ApiError, request };
