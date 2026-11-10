// Incident board: summary numbers, filters, a list sorted by severity, and a form to open a new incident
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { SeverityBadge, StatusBadge } from '../components/Badges';
import { useAuth } from '../hooks/useAuth';
import * as ops from '../services/opsService';
import { SEVERITIES, STATUSES, hasRole, slaText } from '../utils/ops';

const PAGE_SIZE = 15;

function Stats({ stats }) {
  if (!stats) return null;
  const hours = (value) => (value === null ? '-' : `${value}h`);
  return (
    <section className="stats">
      <div className="stat card"><strong>{stats.open_total}</strong><span>open</span></div>
      {SEVERITIES.map((s) => (
        <div key={s} className="stat card"><strong>{stats.open_by_severity[s]}</strong><span>{s}</span></div>
      ))}
      <div className={`stat card${stats.breached ? ' alert' : ''}`}><strong>{stats.breached}</strong><span>past SLA</span></div>
      <div className="stat card"><strong>{stats.unassigned}</strong><span>unassigned</span></div>
      <div className="stat card"><strong>{hours(stats.mtta_hours)}</strong><span>MTTA (30d)</span></div>
      <div className="stat card"><strong>{hours(stats.mttr_hours)}</strong><span>MTTR (30d)</span></div>
    </section>
  );
}

function NewIncident({ onCreated }) {
  const [form, setForm] = useState({ title: '', severity: 'P3', service: '', environment: '', description: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const created = await ops.createIncident({
        title: form.title.trim(),
        severity: form.severity,
        service: form.service.trim() || null,
        environment: form.environment.trim() || null,
        description: form.description.trim() || null,
      });
      onCreated(created);
    } catch (err) {
      setError(err.message || 'Could not open the incident');
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Open an incident</h2>
      <div className="row">
        <div className="field grow">
          <label htmlFor="inc-title">Title</label>
          <input id="inc-title" value={form.title} onChange={set('title')} required maxLength={255} />
        </div>
        <div className="field">
          <label htmlFor="inc-sev">Severity</label>
          <select id="inc-sev" value={form.severity} onChange={set('severity')}>
            {SEVERITIES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
      </div>
      <div className="row">
        <div className="field grow">
          <label htmlFor="inc-service">Service</label>
          <input id="inc-service" value={form.service} onChange={set('service')} maxLength={100} placeholder="e.g. api, database" />
        </div>
        <div className="field grow">
          <label htmlFor="inc-env">Environment</label>
          <input id="inc-env" value={form.environment} onChange={set('environment')} maxLength={50} placeholder="e.g. prod" />
        </div>
      </div>
      <div className="field">
        <label htmlFor="inc-desc">What is happening?</label>
        <textarea id="inc-desc" rows={3} value={form.description} onChange={set('description')} maxLength={5000} />
      </div>
      {error && <p className="error">{error}</p>}
      <button type="submit" className="button" disabled={busy || !form.title.trim()}>Open incident</button>
    </form>
  );
}

export default function IncidentsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [filters, setFilters] = useState({ status: '', severity: '', q: '', mine: false, breached: false });
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState({ items: [], total: 0 });
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [list, summary] = await Promise.all([
        ops.listIncidents({
          status: filters.status,
          severity: filters.severity,
          q: filters.q.trim(),
          assignee: filters.mine ? 'me' : '',
          breached: filters.breached ? true : '',
          limit: PAGE_SIZE,
          offset,
        }),
        ops.getIncidentStats(),
      ]);
      setData(list);
      setStats(summary);
    } catch (err) {
      setError(err.message || 'Could not load incidents');
    } finally {
      setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    load();
  }, [load]);

  const change = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setOffset(0);
    setFilters((f) => ({ ...f, [key]: value }));
  };

  const canEdit = hasRole(user, 'analyst');
  const last = Math.min(offset + PAGE_SIZE, data.total);

  return (
    <div className="stack">
      <Stats stats={stats} />

      {canEdit && (
        <div>
          <button type="button" className="button secondary" onClick={() => setShowForm((s) => !s)}>
            {showForm ? 'Cancel' : 'New incident'}
          </button>
        </div>
      )}
      {showForm && <NewIncident onCreated={(created) => navigate(`/incidents/${created.id}`)} />}

      <section className="card filters-bar">
        <input type="search" placeholder="Search incidents" value={filters.q} onChange={change('q')} aria-label="Search" />
        <select value={filters.status} onChange={change('status')} aria-label="Status">
          <option value="">Any status</option>
          {STATUSES.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={filters.severity} onChange={change('severity')} aria-label="Severity">
          <option value="">Any severity</option>
          {SEVERITIES.map((s) => <option key={s}>{s}</option>)}
        </select>
        <label className="check"><input type="checkbox" checked={filters.mine} onChange={change('mine')} /> Mine</label>
        <label className="check"><input type="checkbox" checked={filters.breached} onChange={change('breached')} /> Past SLA</label>
      </section>

      {error && <p className="error">{error}</p>}
      <section className="card">
        {loading && data.items.length === 0 ? (
          <p className="muted">Loading...</p>
        ) : data.items.length === 0 ? (
          <p className="muted">No incidents match.</p>
        ) : (
          <table className="table">
            <thead>
              <tr><th>Sev</th><th>Title</th><th>Status</th><th>Service</th><th>Assignee</th><th>SLA</th><th>Source</th></tr>
            </thead>
            <tbody>
              {data.items.map((i) => (
                <tr key={i.id}>
                  <td><SeverityBadge severity={i.severity} /></td>
                  <td><Link to={`/incidents/${i.id}`}>{i.title}</Link>{i.occurrences > 1 && <span className="muted"> x{i.occurrences}</span>}</td>
                  <td><StatusBadge status={i.status} /></td>
                  <td>{i.service || '-'}</td>
                  <td>{i.assignee?.email || <span className="muted">unassigned</span>}</td>
                  <td className={i.breached ? 'error' : 'muted'}>{slaText(i)}</td>
                  <td className="muted">{i.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data.total > PAGE_SIZE && (
          <div className="pager">
            <button type="button" className="button secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
            <span className="muted">{offset + 1}-{last} of {data.total}</span>
            <button type="button" className="button secondary" disabled={last >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
          </div>
        )}
      </section>
    </div>
  );
}
