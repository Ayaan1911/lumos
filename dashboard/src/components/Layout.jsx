import { useState, useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  ScrollText,
  FileCode2,
  DollarSign,
  Wifi,
  WifiOff,
} from 'lucide-react';
import axios from 'axios';

const NAV = [
  { to: '/',        icon: <LayoutDashboard size={16} />, label: 'Overview'     },
  { to: '/agents',  icon: <Users size={16} />,           label: 'Agents'       },
  { to: '/audit',   icon: <ScrollText size={16} />,      label: 'Audit Log'    },
  { to: '/policy',  icon: <FileCode2 size={16} />,       label: 'Policy'       },
  { to: '/costs',   icon: <DollarSign size={16} />,      label: 'Costs'        },
];

function useApiHealth() {
  const [ok, setOk] = useState(null);
  useEffect(() => {
    const check = async () => {
      try {
        await axios.get(`${import.meta.env.VITE_API_URL || 'http://localhost:4001'}/health`, { timeout: 3000 });
        setOk(true);
      } catch {
        setOk(false);
      }
    };
    check();
    const id = setInterval(check, 15000);
    return () => clearInterval(id);
  }, []);
  return ok;
}

export default function Layout() {
  const apiOk = useApiHealth();

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#0a0a0a' }}>
      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside style={{
        width: '220px',
        flexShrink: 0,
        background: '#0d0d0d',
        borderRight: '1px solid #1a1a1a',
        display: 'flex',
        flexDirection: 'column',
        padding: '0',
      }}>
        {/* Wordmark */}
        <div style={{
          padding: '20px 20px 16px',
          borderBottom: '1px solid #161616',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}>
          <span style={{ fontSize: '22px', lineHeight: 1 }}>🔦</span>
          <span style={{ fontSize: '17px', fontWeight: '700', color: '#ffffff', letterSpacing: '-0.02em' }}>
            Lumos
          </span>
          <span style={{
            marginLeft: 'auto',
            fontSize: '9px',
            fontWeight: '600',
            color: '#555',
            background: '#161616',
            border: '1px solid #222',
            padding: '2px 5px',
            borderRadius: '3px',
            letterSpacing: '0.05em',
          }}>
            v0.1
          </span>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '12px 10px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {NAV.map(({ to, icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '8px 10px',
                borderRadius: '6px',
                textDecoration: 'none',
                fontSize: '13.5px',
                fontWeight: isActive ? '500' : '400',
                color: isActive ? '#ffffff' : '#666666',
                background: isActive ? '#1a1a1a' : 'transparent',
                transition: 'all 0.12s ease',
              })}
              onMouseEnter={(e) => {
                if (!e.currentTarget.classList.contains('active')) {
                  e.currentTarget.style.background = '#141414';
                  e.currentTarget.style.color = '#aaaaaa';
                }
              }}
              onMouseLeave={(e) => {
                const isActive = e.currentTarget.getAttribute('aria-current') === 'page';
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#666666';
                }
              }}
            >
              <span style={{ opacity: 0.85, flexShrink: 0 }}>{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div style={{
          padding: '14px 16px',
          borderTop: '1px solid #161616',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}>
          <div style={{ fontSize: '11px', color: '#444', fontWeight: '500', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            MCP Firewall
          </div>
          <div style={{ fontSize: '11px', color: '#333' }}>
            Proxy :4000 · API :4001
          </div>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Topbar */}
        <header style={{
          height: '52px',
          flexShrink: 0,
          borderBottom: '1px solid #1a1a1a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          padding: '0 24px',
          gap: '16px',
          background: '#0d0d0d',
        }}>
          {/* Connection status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            {apiOk === null ? (
              <span style={{ color: '#444', fontSize: '12px' }}>Checking…</span>
            ) : apiOk ? (
              <>
                <Wifi size={13} color="#22c55e" />
                <span style={{ fontSize: '12px', color: '#22c55e', fontWeight: '500' }}>API connected</span>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 6px #22c55e88' }} />
              </>
            ) : (
              <>
                <WifiOff size={13} color="#ef4444" />
                <span style={{ fontSize: '12px', color: '#ef4444', fontWeight: '500' }}>API offline</span>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#ef4444' }} />
              </>
            )}
          </div>
        </header>

        {/* Page content */}
        <main style={{ flex: 1, overflow: 'auto', padding: '28px 32px' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

// ─── Shared UI Primitives ───────────────────────────────────────────────────────

export function PageHeader({ title, description, action }) {
  return (
    <div style={{ marginBottom: '24px', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
      <div>
        <h1 style={{ fontSize: '19px', fontWeight: '600', color: '#ffffff', lineHeight: 1.3, letterSpacing: '-0.01em' }}>
          {title}
        </h1>
        {description && (
          <p style={{ marginTop: '4px', fontSize: '13px', color: '#666' }}>{description}</p>
        )}
      </div>
      {action && <div style={{ flexShrink: 0 }}>{action}</div>}
    </div>
  );
}

export function Spinner({ size = 18 }) {
  return (
    <div style={{
      width: size,
      height: size,
      border: `2px solid #1f1f1f`,
      borderTopColor: '#7c3aed',
      borderRadius: '50%',
      animation: 'spin 0.7s linear infinite',
      display: 'inline-block',
      flexShrink: 0,
    }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export function Button({ children, onClick, variant = 'primary', size = 'md', disabled, loading, style: extra }) {
  const styles = {
    primary:   { background: '#7c3aed', color: '#fff',     border: '1px solid #7c3aed',  hoverBg: '#6d28d9' },
    secondary: { background: '#111111', color: '#cccccc',  border: '1px solid #2a2a2a',  hoverBg: '#1a1a1a' },
    danger:    { background: '#ef444418', color: '#ef4444', border: '1px solid #ef444440', hoverBg: '#ef444428' },
    ghost:     { background: 'transparent', color: '#888', border: '1px solid transparent', hoverBg: '#1a1a1a' },
  };
  const s = styles[variant] || styles.primary;
  const pad = size === 'sm' ? '5px 10px' : size === 'lg' ? '10px 20px' : '7px 14px';
  const fs = size === 'sm' ? '12px' : '13px';

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: pad,
        borderRadius: '6px',
        border: s.border,
        background: s.background,
        color: s.color,
        fontSize: fs,
        fontWeight: '500',
        cursor: (disabled || loading) ? 'not-allowed' : 'pointer',
        opacity: (disabled || loading) ? 0.5 : 1,
        transition: 'all 0.12s ease',
        fontFamily: 'inherit',
        whiteSpace: 'nowrap',
        ...extra,
      }}
      onMouseEnter={(e) => { if (!disabled && !loading) e.currentTarget.style.background = s.hoverBg; }}
      onMouseLeave={(e) => { if (!disabled && !loading) e.currentTarget.style.background = s.background; }}
    >
      {loading && <Spinner size={13} />}
      {children}
    </button>
  );
}

export function Table({ columns, data, loading, empty, onRowClick, expandedRow, renderExpanded }) {
  return (
    <div style={{ borderRadius: '8px', border: '1px solid #1f1f1f', overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #1a1a1a', background: '#0d0d0d' }}>
            {columns.map((col) => (
              <th key={col.key} style={{
                padding: '10px 16px',
                textAlign: 'left',
                fontSize: '11px',
                fontWeight: '600',
                color: '#555',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                whiteSpace: 'nowrap',
                width: col.width,
              }}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columns.length} style={{ padding: '40px', textAlign: 'center' }}>
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <Spinner size={22} />
                </div>
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} style={{ padding: '48px 16px', textAlign: 'center', color: '#444', fontSize: '13px' }}>
                {empty || 'No data'}
              </td>
            </tr>
          ) : data.map((row, i) => (
            <>
              <tr
                key={row.id || row.agent_id || row.session_id || i}
                onClick={() => onRowClick && onRowClick(row)}
                style={{
                  borderBottom: '1px solid #161616',
                  cursor: onRowClick ? 'pointer' : 'default',
                  background: expandedRow === (row.id || row.agent_id) ? '#141414' : 'transparent',
                  transition: 'background 0.1s ease',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#141414'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = expandedRow === (row.id || row.agent_id) ? '#141414' : 'transparent'; }}
              >
                {columns.map((col) => (
                  <td key={col.key} style={{
                    padding: '11px 16px',
                    fontSize: '13px',
                    color: col.muted ? '#666' : '#ccc',
                    whiteSpace: col.wrap ? 'normal' : 'nowrap',
                    overflow: 'hidden',
                    textOverflow: col.wrap ? 'unset' : 'ellipsis',
                    maxWidth: col.maxWidth,
                    fontFamily: col.mono ? 'JetBrains Mono, monospace' : 'inherit',
                    fontSize: col.mono ? '12px' : '13px',
                  }}>
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
              {renderExpanded && expandedRow === (row.id || row.agent_id) && (
                <tr key={`exp-${row.id || row.agent_id}`} style={{ background: '#0e0e0e' }}>
                  <td colSpan={columns.length} style={{ padding: '0' }}>
                    {renderExpanded(row)}
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Modal({ open, onClose, title, children, width = '480px' }) {
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: '#111111',
        border: '1px solid #2a2a2a',
        borderRadius: '10px',
        width,
        maxWidth: '95vw',
        maxHeight: '90vh',
        overflow: 'auto',
        boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '18px 22px', borderBottom: '1px solid #1f1f1f',
        }}>
          <h2 style={{ fontSize: '15px', fontWeight: '600', color: '#fff' }}>{title}</h2>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#555', cursor: 'pointer', padding: '2px', lineHeight: 1 }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div style={{ padding: '22px' }}>{children}</div>
      </div>
    </div>
  );
}

export function Input({ label, value, onChange, placeholder, type = 'text', error }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {label && <label style={{ fontSize: '12px', fontWeight: '500', color: '#888' }}>{label}</label>}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          background: '#0a0a0a',
          border: `1px solid ${error ? '#ef4444' : '#2a2a2a'}`,
          borderRadius: '6px',
          padding: '8px 12px',
          color: '#e5e5e5',
          fontSize: '13px',
          fontFamily: 'inherit',
          outline: 'none',
          width: '100%',
          transition: 'border-color 0.12s',
        }}
        onFocus={(e) => { e.target.style.borderColor = '#7c3aed'; }}
        onBlur={(e) => { e.target.style.borderColor = error ? '#ef4444' : '#2a2a2a'; }}
      />
      {error && <span style={{ fontSize: '11px', color: '#ef4444' }}>{error}</span>}
    </div>
  );
}

export function EmptyState({ icon, title, description }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '64px 24px', gap: '12px' }}>
      <div style={{ color: '#2a2a2a', marginBottom: '4px' }}>{icon}</div>
      <div style={{ fontSize: '14px', fontWeight: '500', color: '#444' }}>{title}</div>
      {description && <div style={{ fontSize: '13px', color: '#333', textAlign: 'center', maxWidth: '300px' }}>{description}</div>}
    </div>
  );
}
