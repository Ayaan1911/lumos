export function Badge({ type }) {
  const CONFIG = {
    allow:   { label: 'allow',   bg: '#22c55e18', color: '#22c55e', dot: '#22c55e' },
    allowed: { label: 'allow',   bg: '#22c55e18', color: '#22c55e', dot: '#22c55e' },
    deny:    { label: 'deny',    bg: '#ef444418', color: '#ef4444', dot: '#ef4444' },
    denied:  { label: 'deny',    bg: '#ef444418', color: '#ef4444', dot: '#ef4444' },
    block:   { label: 'block',   bg: '#ef444418', color: '#ef4444', dot: '#ef4444' },
    active:  { label: 'active',  bg: '#22c55e18', color: '#22c55e', dot: '#22c55e' },
    revoked: { label: 'revoked', bg: '#ef444418', color: '#ef4444', dot: '#ef4444' },
    expired: { label: 'expired', bg: '#f59e0b18', color: '#f59e0b', dot: '#f59e0b' },
    issue:   { label: 'issue',   bg: '#7c3aed18', color: '#a78bfa', dot: '#7c3aed' },
    revoke:  { label: 'revoke',  bg: '#ef444418', color: '#ef4444', dot: '#ef4444' },
    error:   { label: 'error',   bg: '#ef444418', color: '#ef4444', dot: '#ef4444' },
  };

  const key = (type || '').toLowerCase();
  const cfg = CONFIG[key] || { label: key, bg: '#1f1f1f', color: '#888888', dot: '#555' };

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '5px',
      padding: '2px 8px',
      borderRadius: '4px',
      background: cfg.bg,
      color: cfg.color,
      fontSize: '11px',
      fontWeight: '500',
      letterSpacing: '0.03em',
      textTransform: 'uppercase',
      whiteSpace: 'nowrap',
    }}>
      <span style={{
        width: '5px',
        height: '5px',
        borderRadius: '50%',
        background: cfg.dot,
        flexShrink: 0,
      }} />
      {cfg.label}
    </span>
  );
}
