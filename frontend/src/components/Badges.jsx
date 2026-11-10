// Coloured labels for an incident's severity and status
export function SeverityBadge({ severity }) {
  return <span className={`badge sev-${severity}`}>{severity}</span>;
}

export function StatusBadge({ status }) {
  return <span className={`badge status-${status}`}>{status}</span>;
}

// Findings use their own scale: critical, high, medium, low, unknown
export function FindingSeverityBadge({ severity }) {
  return <span className={`badge fsev-${severity}`}>{severity}</span>;
}

export function FindingStatusBadge({ status }) {
  return <span className={`badge fstatus-${status}`}>{status}</span>;
}
