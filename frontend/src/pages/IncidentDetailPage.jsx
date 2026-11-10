// One incident: its details, the actions allowed on it, and the timeline of everything that happened
import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { SeverityBadge, StatusBadge } from '../components/Badges';
import { useAuth } from '../hooks/useAuth';
import * as ops from '../services/opsService';
import { NEXT_STATUS, SEVERITIES, formatTime, hasRole, slaText } from '../utils/ops';

export default function IncidentDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [incident, setIncident] = useState(null);
  const [users, setUsers] = useState([]);
  const [note, setNote] = useState('');
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');
  const canEdit = hasRole(user, 'analyst');

  const load = useCallback(async () => {
    try {
      setIncident(await ops.getIncident(id));
      if (canEdit) setUsers(await ops.listUsers());
    } catch (err) {
      setError(err.message || 'Could not load the incident');
    }
  }, [id, canEdit]);

  useEffect(() => {
    load();
  }, [load]);

  // Run an action, show the refreshed incident, or show why it failed
  const act = async (action) => {
    setError('');
    try {
      setIncident(await action());
    } catch (err) {
      setError(err.message || 'That did not work');
    }
  };

  if (!incident) {
    return error ? <p className="error">{error}</p> : <p className="muted">Loading...</p>;
  }

  return (
    <div className="stack">
      <Link to="/incidents">&larr; All incidents</Link>
      <section className="card stack">
        <div className="row">
          <SeverityBadge severity={incident.severity} />
          <StatusBadge status={incident.status} />
          <h2 className="grow">{incident.title}</h2>
        </div>
        {incident.description && <p className="pre-wrap">{incident.description}</p>}
        <dl className="facts">
          <div><dt>Service</dt><dd>{incident.service || '-'}</dd></div>
          <div><dt>Environment</dt><dd>{incident.environment || '-'}</dd></div>
          <div><dt>Source</dt><dd>{incident.source}{incident.occurrences > 1 ? ` (reported ${incident.occurrences} times)` : ''}</dd></div>
          <div><dt>Opened</dt><dd>{formatTime(incident.created_at)}</dd></div>
          <div><dt>Acknowledged</dt><dd>{formatTime(incident.acknowledged_at)}</dd></div>
          <div><dt>Resolved</dt><dd>{formatTime(incident.resolved_at)}</dd></div>
          <div><dt>SLA</dt><dd className={incident.breached ? 'error' : ''}>{slaText(incident)}</dd></div>
        </dl>
        {error && <p className="error">{error}</p>}
      </section>

      {canEdit && (
        <section className="card stack">
          <h3>Actions</h3>
          <div className="row">
            <div className="field grow">
              <label htmlFor="note">Note (optional)</label>
              <input id="note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />
            </div>
            {NEXT_STATUS[incident.status].map((next) => (
              <button
                key={next}
                type="button"
                className="button secondary"
                onClick={() => act(async () => {
                  const updated = await ops.changeStatus(incident.id, next, note);
                  setNote('');
                  return updated;
                })}
              >
                {incident.status === 'resolved' ? 'Reopen' : `Move to ${next}`}
              </button>
            ))}
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="assignee">Assignee</label>
              <select
                id="assignee"
                value={incident.assignee?.id ?? ''}
                onChange={(e) => act(() => ops.updateIncident(incident.id, { assignee_id: e.target.value ? Number(e.target.value) : null }))}
              >
                <option value="">Unassigned</option>
                {users.map((u) => <option key={u.id} value={u.id}>{u.email}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="severity">Severity</label>
              <select id="severity" value={incident.severity} onChange={(e) => act(() => ops.updateIncident(incident.id, { severity: e.target.value }))}>
                {SEVERITIES.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>
        </section>
      )}

      {incident.evidence && (
        <section className="card stack">
          <h3>Evidence from {incident.source}</h3>
          <pre className="code">{JSON.stringify(incident.evidence, null, 2)}</pre>
        </section>
      )}

      <section className="card stack">
        <h3>Timeline</h3>
        <ul className="timeline">
          {incident.events.map((e) => (
            <li key={e.id} className={`event ${e.kind}`}>
              <span className="muted">{formatTime(e.created_at)} &middot; {e.actor}</span>
              <p className="pre-wrap">{e.body}</p>
            </li>
          ))}
        </ul>
        {canEdit && (
          <form
            className="row"
            onSubmit={(e) => {
              e.preventDefault();
              if (!comment.trim()) return;
              act(async () => {
                const updated = await ops.addComment(incident.id, comment.trim());
                setComment('');
                return updated;
              });
            }}
          >
            <input className="grow" value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Add a comment" maxLength={5000} aria-label="Comment" />
            <button type="submit" className="button" disabled={!comment.trim()}>Comment</button>
          </form>
        )}
      </section>
    </div>
  );
}
