import { useCallback, useEffect, useState } from 'react';
import * as taskService from '../services/taskService';

export function useTasks(filters) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await taskService.fetchTasks(filters);
      setTasks(data);
    } catch (err) {
      setError(err.message || 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const addTask = async (task) => {
    const created = await taskService.createTask(task);
    setTasks((prev) => [created, ...prev]);
  };

  const editTask = async (id, updates) => {
    const updated = await taskService.updateTask(id, updates);
    setTasks((prev) => prev.map((task) => (task.id === id ? updated : task)));
  };

  const toggleComplete = async (id) => {
    const updated = await taskService.completeTask(id);
    setTasks((prev) => prev.map((task) => (task.id === id ? updated : task)));
  };

  const removeTask = async (id) => {
    await taskService.deleteTask(id);
    setTasks((prev) => prev.filter((task) => task.id !== id));
  };

  return {
    tasks,
    loading,
    error,
    addTask,
    editTask,
    toggleComplete,
    removeTask,
    reload: loadTasks,
  };
}
