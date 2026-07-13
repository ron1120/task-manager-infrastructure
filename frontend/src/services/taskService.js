// Frontend calls for /api/tasks/... (all need a JWT via request())
import { request } from './api';

export async function fetchTasks({ completed, search } = {}) {
  const params = new URLSearchParams();
  if (completed !== undefined && completed !== 'all') {
    params.set('completed', completed);
  }
  if (search) {
    params.set('search', search);
  }

  const query = params.toString();
  return request(`/api/tasks${query ? `?${query}` : ''}`);
}

export async function createTask(task) {
  return request('/api/tasks', {
    method: 'POST',
    body: JSON.stringify(task),
  });
}

export async function updateTask(id, task) {
  return request(`/api/tasks/${id}`, {
    method: 'PUT',
    body: JSON.stringify(task),
  });
}

export async function completeTask(id) {
  return request(`/api/tasks/${id}/complete`, { method: 'PATCH' });
}

export async function deleteTask(id) {
  return request(`/api/tasks/${id}`, { method: 'DELETE' });
}
