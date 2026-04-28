export function StatCard({ icon, label, value, sub, accentColor }) {
  const color = accentColor || '#7c3aed';

  return (
    <div
      style={{
        position: 'relative',
        overflow: 'hidden',
        background: 'linear-gradient(180deg, rgba(17,17,24,0.96), rgba(12,12,18,0.96))',
        border: '1px solid rgba(124, 58, 237, 0.22)',
        borderRadius: '14px',
        padding: '22px 24px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        flex: 1,
        minWidth: 0,
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04), 0 18px 44px rgba(0,0,0,0.34)',
        transition: 'border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = color;
        e.currentTarget.style.boxShadow = '0 0 20px rgba(124, 58, 237, 0.3), inset 0 1px 0 rgba(255,255,255,0.06)';
        e.currentTarget.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'rgba(124, 58, 237, 0.22)';
        e.currentTarget.style.boxShadow = 'inset 0 1px 0 rgba(255,255,255,0.04), 0 18px 44px rgba(0,0,0,0.34)';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: '0 0 auto 0',
          height: '1px',
          background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
          opacity: 0.75,
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '11px', color: '#9ca3c7', fontWeight: '700', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
          {label}
        </span>
        <span style={{ color, filter: `drop-shadow(0 0 8px ${color}66)` }}>
          {icon}
        </span>
      </div>
      <div>
        <div style={{ fontSize: '34px', fontWeight: '800', color: '#ffffff', lineHeight: 1, letterSpacing: '-0.04em' }}>
          {value ?? <span style={{ color: '#3a3a52', fontSize: '20px' }}>-</span>}
        </div>
        {sub && (
          <div style={{ marginTop: '8px', fontSize: '12px', color: '#73738c' }}>
            {sub}
          </div>
        )}
      </div>
      <div
        style={{
          height: '3px',
          width: '46px',
          borderRadius: '999px',
          background: color,
          boxShadow: `0 0 14px ${color}88`,
        }}
      />
    </div>
  );
}
