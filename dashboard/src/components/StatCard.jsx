export function StatCard({ icon, label, value, sub, accentColor }) {
  return (
    <div style={{
      background: '#111111',
      border: '1px solid #1f1f1f',
      borderRadius: '8px',
      padding: '20px 24px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      flex: 1,
      minWidth: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '12px', color: '#888888', fontWeight: '500', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
          {label}
        </span>
        <span style={{ color: accentColor || '#555555' }}>
          {icon}
        </span>
      </div>
      <div>
        <div style={{ fontSize: '28px', fontWeight: '600', color: accentColor || '#ffffff', lineHeight: 1 }}>
          {value ?? <span style={{ color: '#333', fontSize: '20px' }}>—</span>}
        </div>
        {sub && (
          <div style={{ marginTop: '6px', fontSize: '12px', color: '#555555' }}>
            {sub}
          </div>
        )}
      </div>
    </div>
  );
}
