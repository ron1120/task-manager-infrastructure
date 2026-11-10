// Frontend calls for the incident tracker: /api/incidents, /api/users, /api/api-keys, /api/audit
import { request } from './api';

function query(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '' && value !== false) {
      search.set(key, String(value));
    }
  });
  const text = search.toString();
  return text ? `?${text}` : '';
}

export const listIncidents = (params) => request(`/api/incidents${query(params)}`);
export const getIncidentStats = () => request('/api/incidents/stats');
export const getIncident = (id) => request(`/api/incidents/${id}`);
export const createIncident = (body) =>
  request('/api/incidents', { method: 'POST', body: JSON.stringify(body) });
export const updateIncident = (id, body) =>
  request(`/api/incidents/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
export const changeStatus = (id, status, note) =>
  request(`/api/incidents/${id}/status`, {
    method: 'POST',
    body: JSON.stringify({ status, note: note || null }),
  });
export const addComment = (id, body) =>
  request(`/api/incidents/${id}/comments`, { method: 'POST', body: JSON.stringify({ body }) });

export const listUsers = () => request('/api/users');
export const changeRole = (id, role) =>
  request(`/api/users/${id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) });

export const listApiKeys = () => request('/api/api-keys');
export const createApiKey = (name, source) =>
  request('/api/api-keys', { method: 'POST', body: JSON.stringify({ name, source }) });
export const revokeApiKey = (id) => request(`/api/api-keys/${id}`, { method: 'DELETE' });

export const listAudit = (params) => request(`/api/audit${query(params)}`);
