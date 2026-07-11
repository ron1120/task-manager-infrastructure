export default function TaskFilters({ filters, onChange }) {
  return (
    <section className="card filters">
      <div className="field">
        <label htmlFor="search">Search</label>
        <input
          id="search"
          type="search"
          placeholder="Search tasks..."
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor="status">Status</label>
        <select
          id="status"
          value={filters.completed}
          onChange={(e) => onChange({ ...filters, completed: e.target.value })}
        >
          <option value="all">All</option>
          <option value="false">Active</option>
          <option value="true">Completed</option>
        </select>
      </div>
    </section>
  );
}
