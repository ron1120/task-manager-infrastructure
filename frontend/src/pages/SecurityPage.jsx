// Security findings from scanners (Trivy, gitleaks, Hadolint): what is open, what has a fix, what was accepted
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FindingSeverityBadge, FindingStatusBadge } from '../components/Badges';
import { useAuth } from '../hooks/useAuth';
import * as ops from '../services/opsService';
import { formatTime, hasRole } from '../utils/ops';

const PAGE_SIZE = 15;
const SEVERITIES = ['critical', 'high', 'medium', 'low', 'unknown'];
const KINDS = ['vulnerability', 'secret', 'misconfig', 'lint'];

function Stats({ stats }) {
  if (!stats) return null;
  const bySeverity = stats.open_by_severity;
  return (
    <section className="stats">
      <div className="stat card"><strong>{stats.open_total}</strong><span>open</span></div>
      <div className={`stat card${bySeverity.critical ? ' alert' : ''}`}><strong>{bySeverity.critical}</strong><span>critical</span></div>
      <div className="stat card"><strong>{bySeverity.high}</strong><span>high</span></div>
      <div className="stat card"><strong>{bySeverity.medium}</strong><span>medium</span></div>
      <div className="stat card"><strong>{bySeverity.low}</strong><span>low</span></div>
      <div className="stat card"><strong>{stats.fixable_open}</strong><span>fix available</span></div>
      <div className={`stat card${stats.open_by_kind.secret ? ' alert' : ''}`}><strong>{stats.open_by_kind.secret || 0}</strong><span>secrets</span></div>
      <div className="stat card">
        <strong>{stats.oldest_open_critical_days === null ? '-' : `${stats.oldest_open_critical_days}d`}</strong>
        <span>oldest critical</span>
      </div>
    </section>
  );
}

function FindingRow({ finding, canEdit, onChanged }) {
  const navigate = useNavigate();
  const [accepting, setAccepting] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');

  const run = async (action) => {
    setError('');
    try {
      await action();
      setAccepting(false);
      setReason('');
      onChanged();
    } catch (err) {
      setError(err.message || 'That did not work');
    }
  };

  const what = finding.package
    ? `${finding.package} ${finding.installed_version || ''}${finding.fixed_version ? ` -> ${finding.fixed_version}` : ''}`
    : finding.location;

  return (
    <>
      <tr>
        <td><FindingSeverityBadge severity={finding.severity} /></td>
        <td>
          {finding.url ? <a href={finding.url} target="_blank" rel="noopener noreferrer">{finding.rule_id}</a> : finding.rule_id}
          <div className="muted small">{finding.kind} &middot; {finding.scanner}</div>
        </td>
        <td>
          <div>{what}</div>
          <div className="muted small">{finding.title}</div>
          {finding.status === 'accepted' && <div className="muted small">Accepted by {finding.status_by}: {finding.status_reason}</div>}
          {finding.package && finding.location && <div className="muted small">{finding.location}</div>}
        </td>
        <td className="muted">{finding.target}</td>
        <td><FindingStatusBadge status={finding.status} /></td>
        <td className="muted small">{formatTime(finding.last_seen_at)}</td>
        <td className="actions-cell">
          {canEdit && finding.status === 'open' && (
            <button type="button" className="button secondary" onClick={() => setAccepting((a) => !a)}>Accept risk</button>
          )}
          {canEdit && finding.status === 'accepted' && (
            <button type="button" className="button secondary" onClick={() => run(() => ops.setFindingStatus(finding.id, 'open'))}>Reopen</button>
          )}
          {finding.incident_id ? (
            <Link to={`/incidents/${finding.incident_id}`} className="small">incident #{finding.incident_id}</Link>
          ) : (
            canEdit && finding.status !== 'fixed' && (
              <button type="button" className="button secondary" onClick={() => run(async () => navigate(`/incidents/${(await ops.openFindingIncident(finding.id)).id}`))}>
                Open incident
              </button>
            )
          )}
        </td>
      </tr>
      {accepting && (
        <tr>
          <td colSpan={7}>
            <form className="row" onSubmit={(e) => { e.preventDefault(); run(() => ops.setFindingStatus(finding.id, 'accepted', reason)); }}>
              <input className="grow" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why is this acceptable? (recorded in the audit log)" maxLength={2000} aria-label="Reason" />
              <button type="submit" className="button" disabled={reason.trim().length < 5}>Accept</button>
              <button type="button" className="button secondary" onClick={() => setAccepting(false)}>Cancel</button>
            </form>
          </td>
        </tr>
      )}
      {error && <tr><td colSpan={7} className="error">{error}</td></tr>}
    </>
  );
}

export default function SecurityPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState({ status: 'open', severity: '', kind: '', q: '', fixable: false });
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState({ items: [], total: 0 });
  const [stats, setStats] = useState(null);
  const [scans, setScans] = useState([]);
  const [error, setError] = useState('');
  const canEdit = hasRole(user, 'analyst');

  const load = useCallback(async () => {
    try {
      const [list, summary, recent] = await Promise.all([
        ops.listFindings({
          status: filters.status, severity: filters.severity, kind: filters.kind, q: filters.q.trim(),
          fixable: filters.fixable ? true : '', limit: PAGE_SIZE, offset,
        }),
        ops.getFindingStats(),
        ops.listScans(8),
      ]);
      setData(list);
      setStats(summary);
      setScans(recent);
      setError('');
    } catch (err) {
      setError(err.message || 'Could not load findings');
    }
  }, [filters, offset]);

  useEffect(() => {
    load();
  }, [load]);

  const change = (key) => (e) => {
    setOffset(0);
    setFilters((f) => ({ ...f, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));
  };
  const last = Math.min(offset + PAGE_SIZE, data.total);

  return (
    <div className="stack">
      <Stats stats={stats} />

      <section className="card filters-bar">
        <input type="search" placeholder="Search CVE, package or file" value={filters.q} onChange={change('q')} aria-label="Search" />
        <select value={filters.status} onChange={change('status')} aria-label="Status">
          <option value="">Any status</option>
          <option value="open">open</option>
          <option value="accepted">accepted</option>
          <option value="fixed">fixed</option>
        </select>
        <select value={filters.severity} onChange={change('severity')} aria-label="Severity">
          <option value="">Any severity</option>
          {SEVERITIES.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={filters.kind} onChange={change('kind')} aria-label="Kind">
          <option value="">Any kind</option>
          {KINDS.map((k) => <option key={k}>{k}</option>)}
        </select>
        <label className="check"><input type="checkbox" checked={filters.fixable} onChange={change('fixable')} /> Fix available</label>
      </section>

      {error && <p className="error">{error}</p>}
      <section className="card">
        {data.items.length === 0 ? (
          <p className="muted">No findings match. Upload scanner output to /api/intake/scan/&lt;scanner&gt; (see the README).</p>
        ) : (
          <table className="table">
            <thead><tr><th>Sev</th><th>Rule</th><th>What</th><th>Target</th><th>Status</th><th>Last seen</th><th /></tr></thead>
            <tbody>
              {data.items.map((f) => <FindingRow key={f.id} finding={f} canEdit={canEdit} onChanged={load} />)}
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

      <section className="card stack">
        <h2>Recent scans</h2>
        <table className="table">
          <thead><tr><th>When</th><th>Scanner</th><th>Target</th><th>Found</th><th>New</th><th>Fixed</th><th>Commit</th></tr></thead>
          <tbody>
            {scans.map((s) => (
              <tr key={s.id}>
                <td className="muted">{formatTime(s.created_at)}</td>
                <td>{s.scanner}</td>
                <td>{s.run_url ? <a href={s.run_url} target="_blank" rel="noopener noreferrer">{s.target}</a> : s.target}</td>
                <td>{s.total}</td>
                <td>{s.new_count}</td>
                <td>{s.fixed_count}</td>
                <td className="muted"><code>{s.ref ? s.ref.slice(0, 7) : '-'}</code></td>
              </tr>
            ))}
            {scans.length === 0 && <tr><td colSpan={7} className="muted">No scans uploaded yet.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
