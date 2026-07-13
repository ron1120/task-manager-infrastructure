// Main tasks screen — filters + form + list
import { useMemo, useState } from 'react';
import TaskFilters from '../components/TaskFilters';
import TaskForm from '../components/TaskForm';
import TaskList from '../components/TaskList';
import { useTasks } from '../hooks/useTasks';

export default function TasksPage() {
  const [filters, setFilters] = useState({ search: '', completed: 'all' });

  // Shape filters for the API hook
  const queryFilters = useMemo(
    () => ({
      search: filters.search || undefined,
      completed: filters.completed,
    }),
    [filters],
  );

  const { tasks, loading, error, addTask, editTask, toggleComplete, removeTask } =
    useTasks(queryFilters);

  return (
    <div className="tasks-page stack">
      <TaskForm onSubmit={addTask} />
      <TaskFilters filters={filters} onChange={setFilters} />
      <TaskList
        tasks={tasks}
        loading={loading}
        error={error}
        onToggleComplete={toggleComplete}
        onUpdate={editTask}
        onDelete={removeTask}
      />
    </div>
  );
}
