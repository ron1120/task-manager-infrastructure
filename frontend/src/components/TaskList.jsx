import TaskItem from './TaskItem';

export default function TaskList({ tasks, loading, error, onToggleComplete, onUpdate, onDelete }) {
  if (loading) {
    return <div className="card">Loading tasks...</div>;
  }

  if (error) {
    return <div className="card error">{error}</div>;
  }

  if (!tasks.length) {
    return <div className="card muted">No tasks found.</div>;
  }

  return (
    <section className="stack">
      {tasks.map((task) => (
        <TaskItem
          key={task.id}
          task={task}
          onToggleComplete={onToggleComplete}
          onUpdate={onUpdate}
          onDelete={onDelete}
        />
      ))}
    </section>
  );
}
