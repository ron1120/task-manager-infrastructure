// Admin only: API keys for machine callers, user roles, and the audit log
import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import * as ops from '../services/opsService';
import { formatTime } from '../utils/ops';

const SOURCES = ['github_actions', 'alertmanager', 'ci_triage', 'generic'];
const ROLES = ['viewer', 'analyst', 'admin'];
const AUDIT_PAGE = 20;

function ApiKeys() {
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState('');
  const [source, setSource] = useState(SOURCES[0]);
  const [created, setCreated] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setKeys(await ops.listApiKeys());
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = async (e) => {
    e.preventDefault();
    setError('');
    try {
      setCreated(await ops.createApiKey(name.trim(), source));
      setName('');
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const revoke = async (id) => {
    await ops.revokeApiKey(id);
    load();
  };

  return (
    <section className="card stack">
      <h2>API keys</h2>
      <p className="muted">Machines (CI, Alertmanager, the triage agent) report incidents with a key. Each key works for one source only.</p>
      <form className="row" onSubmit={create}>
        <div className="field grow">
          <label htmlFor="key-name">Name</label>
          <input id="key-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="e.g. github-ci" required />
        </div>
        <div className="field">
          <label htmlFor="key-source">Source</label>
          <select id="key-source" value={source} onChange={(e) => setSource(e.target.value)}>
            {SOURCES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <button type="submit" className="button" disabled={!name.trim()}>Create key</button>
      </form>
      {error && <p className="error">{error}</p>}
      {created && (
        <div className="callout">
          <strong>Copy this key now. It is shown only once.</strong>
          <code className="secret">{created.key}</code>
          <button type="button" className="button secondary" onClick={() => navigator.clipboard?.writeText(created.key)}>Copy</button>
          <button type="button" className="button secondary" onClick={() => setCreated(null)}>Done</button>
        </div>
      )}
      <table className="table">
        <thead><tr><th>Name</th><th>Source</th><th>Key</th><th>Last used</th><th /></tr></thead>
        <tbody>
          {keys.map((k) => (
            <tr key={k.id}>
              <td>{k.name}</td>
              <td>{k.source}</td>
              <td><code>{k.prefix}...</code></td>
              <td className="muted">{formatTime(k.last_used_at)}</td>
              <td>
                {k.revoked_at ? <span className="muted">revoked</span> : (
                  <button type="button" className="button danger" onClick={() => revoke(k.id)}>Revoke</button>
                )}
              </td>
            </tr>
          ))}
          {keys.length === 0 && <tr><td colSpan={5} className="muted">No keys yet.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}

function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setUsers(await ops.listUsers());
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const change = async (id, role) => {
    setError('');
    try {
      await ops.changeRole(id, role);
    } catch (err) {
      setError(err.message);
    }
    load();
  };

  return (
    <section className="card stack">
      <h2>Users and roles</h2>
      <p className="muted">Viewers can read. Analysts can also change incidents. Admins can also manage keys, roles and the audit log.</p>
      {error && <p className="error">{error}</p>}
      <table className="table">
        <thead><tr><th>Email</th><th>Role</th></tr></thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.email}{u.id === me.id && <span className="muted"> (you)</span>}</td>
              <td>
                <select value={u.role} onChange={(e) => change(u.id, e.target.value)} aria-label={`Role for ${u.email}`}>
                  {ROLES.map((r) => <option key={r}>{r}</option>)}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function AuditLog() {
  const [filters, setFilters] = useState({ action: '', actor: '' });
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState({ items: [], total: 0 });
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setData(await ops.listAudit({ action: filters.action.trim(), actor: filters.actor.trim(), limit: AUDIT_PAGE, offset }));
      setError('');
    } catch (err) {
      setError(err.message);
    }
  }, [filters, offset]);

  useEffect(() => {
    load();
  }, [load]);

  const change = (key) => (e) => {
    setOffset(0);
    setFilters((f) => ({ ...f, [key]: e.target.value }));
  };
  const last = Math.min(offset + AUDIT_PAGE, data.total);

  return (
    <section className="card stack">
      <h2>Audit log</h2>
      <p className="muted">Every change, and who made it. Entries can be read but never edited or deleted.</p>
      <div className="row">
        <input className="grow" placeholder="Action, e.g. incident.create" value={filters.action} onChange={change('action')} aria-label="Action" />
        <input className="grow" placeholder="Actor, e.g. key:github-ci" value={filters.actor} onChange={change('actor')} aria-label="Actor" />
      </div>
      {error && <p className="error">{error}</p>}
      <table className="table">
        <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Entity</th><th>Details</th><th>IP</th></tr></thead>
        <tbody>
          {data.items.map((e) => (
            <tr key={e.id}>
              <td className="muted">{formatTime(e.created_at)}</td>
              <td>{e.actor}</td>
              <td><code>{e.action}</code></td>
              <td>{e.entity_type}{e.entity_id ? ` #${e.entity_id}` : ''}</td>
              <td className="muted">{e.details ? JSON.stringify(e.details) : ''}</td>
              <td className="muted">{e.ip || ''}</td>
            </tr>
          ))}
          {data.items.length === 0 && <tr><td colSpan={6} className="muted">No entries.</td></tr>}
        </tbody>
      </table>
      {data.total > AUDIT_PAGE && (
        <div className="pager">
          <button type="button" className="button secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - AUDIT_PAGE))}>Newer</button>
          <span className="muted">{offset + 1}-{last} of {data.total}</span>
          <button type="button" className="button secondary" disabled={last >= data.total} onClick={() => setOffset(offset + AUDIT_PAGE)}>Older</button>
        </div>
      )}
    </section>
  );
}

export default function AdminPage() {
  return (
    <div className="stack">
      <ApiKeys />
      <Users />
      <AuditLog />
    </div>
  );
}
