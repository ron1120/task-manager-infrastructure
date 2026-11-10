// Coloured labels for an incident's severity and status
export function SeverityBadge({ severity }) {
  return <span className={`badge sev-${severity}`}>{severity}</span>;
}

export function StatusBadge({ status }) {
  return <span className={`badge status-${status}`}>{status}</span>;
}
