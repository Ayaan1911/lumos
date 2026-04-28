export function Badge({ type }) {
  const CONFIG = {
    allow:   { label: 'allow',   bg: '#22c55e18', color: '#4ade80', dot: '#22c55e', border: '#22c55e40' },
    allowed: { label: 'allow',   bg: '#22c55e18', color: '#4ade80', dot: '#22c55e', border: '#22c55e40' },
    deny:    { label: 'deny',    bg: '#ef444418', color: '#fb7185', dot: '#ef4444', border: '#ef444450' },
    denied:  { label: 'deny',    bg: '#ef444418', color: '#fb7185', dot: '#ef4444', border: '#ef444450' },
    block:   { label: 'block',   bg: '#ef444418', color: '#fb7185', dot: '#ef4444', border: '#ef444450' },
    active:  { label: 'active',  bg: '#22c55e18', color: '#4ade80', dot: '#22c55e', border: '#22c55e40' },
    revoked: { label: 'revoked', bg: '#ef444418', color: '#fb7185', dot: '#ef4444', border: '#ef444450' },
    expired: { label: 'expired', bg: '#f59e0b18', color: '#fbbf24', dot: '#f59e0b', border: '#f59e0b45' },
    issue:   { label: 'issue',   bg: '#7c3aed20', color: '#c4b5fd', dot: '#7c3aed', border: '#7c3aed55' },
    revoke:  { label: 'revoke',  bg: '#ef444418', color: '#fb7185', dot: '#ef4444', border: '#ef444450' },
    error:   { label: 'error',   bg: '#ef444418', color: '#fb7185', dot: '#ef4444', border: '#ef444450' },
  };

  const key = (type || '').toLowerCase();
  const cfg = CONFIG[key] || { label: key, bg: '#171724', color: '#a1a1b5', dot: '#06b6d4', border: '#23233a' };

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '5px',
      padding: '3px 9px',
      borderRadius: '999px',
      border: `1px solid ${cfg.border}`,
      background: cfg.bg,
      color: cfg.color,
      fontSize: '10px',
      fontWeight: '700',
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
      whiteSpace: 'nowrap',
      boxShadow: `0 0 12px ${cfg.dot}18`,
    }}>
      <span style={{
        width: '5px',
        height: '5px',
        borderRadius: '50%',
        background: cfg.dot,
        boxShadow: `0 0 8px ${cfg.dot}`,
        flexShrink: 0,
      }} />
      {cfg.label}
    </span>
  );
}
