import { useState } from 'react';

export default function TaskItem({ task, onToggleComplete, onUpdate, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description || '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onUpdate(task.id, {
        title: title.trim(),
        description: description.trim() || null,
      });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className={`task-item ${task.completed ? 'completed' : ''}`}>
      <div className="task-main">
        <input
          type="checkbox"
          checked={task.completed}
          onChange={() => onToggleComplete(task.id)}
          aria-label={`Mark ${task.title} as complete`}
        />
        {editing ? (
          <div className="stack grow">
            <input value={title} onChange={(e) => setTitle(e.target.value)} />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </div>
        ) : (
          <div className="grow">
            <h3>{task.title}</h3>
            {task.description && <p className="muted">{task.description}</p>}
          </div>
        )}
      </div>
      <div className="task-actions">
        {editing ? (
          <>
            <button type="button" className="button" onClick={handleSave} disabled={saving}>
              Save
            </button>
            <button type="button" className="button secondary" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button type="button" className="button secondary" onClick={() => setEditing(true)}>
              Edit
            </button>
            <button type="button" className="button danger" onClick={() => onDelete(task.id)}>
              Delete
            </button>
          </>
        )}
      </div>
    </article>
  );
}
