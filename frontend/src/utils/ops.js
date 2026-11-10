// Small helpers shared by the incident pages

const RANK = { viewer: 0, analyst: 1, admin: 2 };

// Does this user have at least the given role?
export function hasRole(user, minimum) {
  return (RANK[user?.role] ?? -1) >= RANK[minimum];
}

// Which status may follow which (mirrors TRANSITIONS in backend/app/models/ops.py).
export const NEXT_STATUS = {
  open: ['triaged', 'resolved'],
  triaged: ['mitigated', 'resolved', 'open'],
  mitigated: ['resolved', 'triaged'],
  resolved: ['open'],
};

export const SEVERITIES = ['P1', 'P2', 'P3', 'P4'];
export const STATUSES = ['open', 'triaged', 'mitigated', 'resolved'];

export function formatTime(value) {
  return value ? new Date(value).toLocaleString() : '-';
}

// "due in 3h", "breached 2h ago", or "closed" once resolved
export function slaText(incident) {
  if (incident.status === 'resolved') return 'closed';
  const hours = (new Date(incident.sla_due_at) - new Date()) / 3600000;
  const abs = Math.abs(hours);
  const amount = abs >= 48 ? `${Math.round(abs / 24)}d` : abs >= 1 ? `${Math.round(abs)}h` : `${Math.round(abs * 60)}m`;
  return hours >= 0 ? `due in ${amount}` : `breached ${amount} ago`;
}
