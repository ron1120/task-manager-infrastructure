// JWT storage helpers — token lives in localStorage (not cookies)
const TOKEN_KEY = 'task_manager_token';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  // Called after successful login
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  // Called on logout or when /me fails (bad/expired token)
  localStorage.removeItem(TOKEN_KEY);
}
