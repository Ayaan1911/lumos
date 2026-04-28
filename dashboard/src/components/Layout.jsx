import { useState, useEffect, Fragment } from 'react';
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
  { to: '/',        icon: <LayoutDashboard size={16} />, label: 'Overview'  },
  { to: '/agents',  icon: <Users size={16} />,           label: 'Agents'    },
  { to: '/audit',   icon: <ScrollText size={16} />,      label: 'Audit Log' },
  { to: '/policy',  icon: <FileCode2 size={16} />,       label: 'Policy'    },
  { to: '/costs',   icon: <DollarSign size={16} />,      label: 'Costs'     },
];

const theme = {
  bg: '#0a0a0f',
  sidebar: '#07070c',
  surface: '#111118',
  surface2: '#171724',
  border: '#23233a',
  borderHot: '#7c3aed66',
  text: '#ffffff',
  muted: '#a1a1b5',
  dim: '#62627a',
  purple: '#7c3aed',
  cyan: '#06b6d4',
  green: '#22c55e',
  red: '#ef4444',
};

function useApiHealth() {
  const [ok, setOk] = useState(null);
  useEffect(() => {
    const check = async () => {
      try {
        await axios.get(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:4001'}/health`, { timeout: 3000 });
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
    <div style={{
      display: 'flex',
      height: '100vh',
      overflow: 'hidden',
      background: 'transparent',
      position: 'relative',
      zIndex: 1,
    }}>
      <aside style={{
        width: '244px',
        flexShrink: 0,
        background: 'linear-gradient(180deg, rgba(7,7,12,0.98), rgba(10,10,18,0.98))',
        borderRight: '1px solid rgba(124, 58, 237, 0.24)',
        boxShadow: '18px 0 60px rgba(0,0,0,0.38), inset -1px 0 0 rgba(6,182,212,0.08)',
        display: 'flex',
        flexDirection: 'column',
        padding: 0,
      }}>
        <div style={{
          padding: '24px 22px 20px',
          borderBottom: '1px solid rgba(124, 58, 237, 0.18)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{
              width: '34px',
              height: '34px',
              borderRadius: '10px',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'linear-gradient(135deg, #7c3aed, #06b6d4)',
              boxShadow: '0 0 24px rgba(124, 58, 237, 0.42)',
              color: '#fff',
              fontWeight: 900,
              letterSpacing: '-0.06em',
            }}>
              L
            </span>
            <div>
              <div style={{ fontSize: '18px', fontWeight: '800', color: theme.text, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                Lumos
              </div>
              <div style={{ marginTop: '1px', fontSize: '10px', color: theme.cyan, letterSpacing: '0.18em', textTransform: 'uppercase' }}>
                SOC Control
              </div>
            </div>
            <span style={{
              marginLeft: 'auto',
              fontSize: '9px',
              fontWeight: '700',
              color: '#c4b5fd',
              background: '#7c3aed1f',
              border: '1px solid #7c3aed55',
              padding: '3px 6px',
              borderRadius: '999px',
              letterSpacing: '0.08em',
            }}>
              v0.1
            </span>
          </div>
        </div>

        <nav style={{ flex: 1, padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {NAV.map(({ to, icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '11px',
                padding: '11px 12px',
                borderRadius: '10px',
                borderLeft: `3px solid ${isActive ? theme.purple : 'transparent'}`,
                textDecoration: 'none',
                fontSize: '12px',
                fontWeight: '700',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: isActive ? theme.text : '#77778f',
                background: isActive ? 'linear-gradient(90deg, rgba(124,58,237,0.24), rgba(6,182,212,0.06))' : 'transparent',
                boxShadow: isActive ? '0 0 20px rgba(124, 58, 237, 0.22)' : 'none',
                transition: 'all 0.16s ease',
              })}
              onMouseEnter={(e) => {
                if (e.currentTarget.getAttribute('aria-current') !== 'page') {
                  e.currentTarget.style.background = 'rgba(124,58,237,0.08)';
                  e.currentTarget.style.color = '#c7c7da';
                }
              }}
              onMouseLeave={(e) => {
                if (e.currentTarget.getAttribute('aria-current') !== 'page') {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#77778f';
                }
              }}
            >
              <span style={{ color: 'currentColor', flexShrink: 0, filter: 'drop-shadow(0 0 7px rgba(124,58,237,0.35))' }}>{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div style={{
          margin: '0 14px 14px',
          padding: '14px 14px',
          border: '1px solid rgba(6, 182, 212, 0.18)',
          borderRadius: '12px',
          background: 'linear-gradient(180deg, rgba(17,17,24,0.84), rgba(8,8,14,0.84))',
        }}>
          <div style={{ fontSize: '10px', color: '#06b6d4', fontWeight: '800', letterSpacing: '0.16em', textTransform: 'uppercase' }}>
            MCP Firewall
          </div>
          <div style={{ marginTop: '7px', fontSize: '11px', color: '#73738c', fontFamily: 'JetBrains Mono, monospace' }}>
            Proxy :4000 / API :4001
          </div>
        </div>
      </aside>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <header style={{
          height: '58px',
          flexShrink: 0,
          borderBottom: '1px solid rgba(124, 58, 237, 0.18)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          padding: '0 30px',
          gap: '16px',
          background: 'rgba(10,10,15,0.72)',
          backdropFilter: 'blur(18px)',
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '9px',
            padding: '7px 11px',
            borderRadius: '999px',
            background: apiOk ? '#22c55e12' : apiOk === false ? '#ef444412' : '#171724',
            border: `1px solid ${apiOk ? '#22c55e40' : apiOk === false ? '#ef444440' : '#23233a'}`,
          }}>
            {apiOk === null ? (
              <span style={{ color: theme.dim, fontSize: '12px', letterSpacing: '0.08em', textTransform: 'uppercase' }}>Checking</span>
            ) : apiOk ? (
              <>
                <Wifi size={13} color={theme.green} />
                <span style={{ fontSize: '11px', color: '#4ade80', fontWeight: '800', letterSpacing: '0.1em', textTransform: 'uppercase' }}>API connected</span>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: theme.green, boxShadow: '0 0 10px #22c55e' }} />
              </>
            ) : (
              <>
                <WifiOff size={13} color={theme.red} />
                <span style={{ fontSize: '11px', color: '#fb7185', fontWeight: '800', letterSpacing: '0.1em', textTransform: 'uppercase' }}>API offline</span>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: theme.red, boxShadow: '0 0 10px #ef4444' }} />
              </>
            )}
          </div>
        </header>

        <main style={{
          flex: 1,
          overflow: 'auto',
          padding: '30px 34px',
          background: 'linear-gradient(135deg, rgba(10,10,15,0.52), rgba(12,9,20,0.72))',
        }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function PageHeader({ title, description, action }) {
  return (
    <div style={{ marginBottom: '26px', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '18px' }}>
      <div>
        <div style={{ fontSize: '10px', fontWeight: '800', color: theme.cyan, letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: '7px' }}>
          Lumos Security Console
        </div>
        <h1 style={{ fontSize: '24px', fontWeight: '800', color: theme.text, lineHeight: 1.15, letterSpacing: '-0.03em' }}>
          {title}
        </h1>
        {description && (
          <p style={{ marginTop: '7px', fontSize: '13px', color: theme.muted }}>{description}</p>
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
      border: '2px solid rgba(124,58,237,0.16)',
      borderTopColor: theme.cyan,
      borderRightColor: theme.purple,
      borderRadius: '50%',
      animation: 'spin 0.7s linear infinite',
      display: 'inline-block',
      flexShrink: 0,
      boxShadow: '0 0 16px rgba(6,182,212,0.22)',
    }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export function Button({ children, onClick, variant = 'primary', size = 'md', disabled, loading, style: extra }) {
  const styles = {
    primary: {
      background: 'linear-gradient(135deg, #7c3aed, #06b6d4)',
      color: '#fff',
      border: '1px solid rgba(124,58,237,0.65)',
      hoverBg: 'linear-gradient(135deg, #8b5cf6, #22d3ee)',
      shadow: '0 0 18px rgba(124,58,237,0.24)',
      hoverShadow: '0 0 24px rgba(124,58,237,0.45)',
    },
    secondary: {
      background: '#111118',
      color: '#c7c7da',
      border: '1px solid rgba(124,58,237,0.28)',
      hoverBg: '#171724',
      shadow: 'none',
      hoverShadow: '0 0 18px rgba(124,58,237,0.18)',
    },
    danger: {
      background: '#ef444418',
      color: '#fb7185',
      border: '1px solid #ef444450',
      hoverBg: '#ef444428',
      shadow: 'none',
      hoverShadow: '0 0 18px rgba(239,68,68,0.22)',
    },
    ghost: {
      background: 'transparent',
      color: '#9ca3c7',
      border: '1px solid transparent',
      hoverBg: '#171724',
      shadow: 'none',
      hoverShadow: 'none',
    },
  };
  const s = styles[variant] || styles.primary;
  const pad = size === 'sm' ? '6px 11px' : size === 'lg' ? '11px 21px' : '8px 15px';
  const fs = size === 'sm' ? '11px' : '12px';

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '7px',
        padding: pad,
        borderRadius: '9px',
        border: s.border,
        background: s.background,
        color: s.color,
        fontSize: fs,
        fontWeight: '800',
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        cursor: (disabled || loading) ? 'not-allowed' : 'pointer',
        opacity: (disabled || loading) ? 0.52 : 1,
        transition: 'all 0.16s ease',
        fontFamily: 'inherit',
        whiteSpace: 'nowrap',
        boxShadow: s.shadow,
        ...extra,
      }}
      onMouseEnter={(e) => {
        if (!disabled && !loading) {
          e.currentTarget.style.background = s.hoverBg;
          e.currentTarget.style.boxShadow = s.hoverShadow;
          e.currentTarget.style.transform = 'translateY(-1px)';
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled && !loading) {
          e.currentTarget.style.background = s.background;
          e.currentTarget.style.boxShadow = s.shadow;
          e.currentTarget.style.transform = 'translateY(0)';
        }
      }}
    >
      {loading && <Spinner size={13} />}
      {children}
    </button>
  );
}

export function Table({ columns, data, loading, empty, onRowClick, expandedRow, renderExpanded }) {
  return (
    <div style={{
      borderRadius: '14px',
      border: '1px solid rgba(124,58,237,0.22)',
      overflow: 'hidden',
      background: 'rgba(17,17,24,0.86)',
      boxShadow: '0 18px 44px rgba(0,0,0,0.30)',
    }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(124,58,237,0.18)', background: 'rgba(7,7,12,0.88)' }}>
            {columns.map((col) => (
              <th key={col.key} style={{
                padding: '12px 16px',
                textAlign: 'left',
                fontSize: '10px',
                fontWeight: '800',
                color: '#8b8ba4',
                letterSpacing: '0.12em',
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
              <td colSpan={columns.length} style={{ padding: '44px', textAlign: 'center' }}>
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <Spinner size={22} />
                </div>
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} style={{ padding: '52px 16px', textAlign: 'center', color: theme.dim, fontSize: '13px' }}>
                {empty || 'No data'}
              </td>
            </tr>
          ) : data.map((row, i) => (
            <Fragment key={row.id || row.agent_id || row.session_id || i}>
              <tr
                onClick={() => onRowClick && onRowClick(row)}
                style={{
                  borderBottom: '1px solid rgba(35,35,58,0.58)',
                  cursor: onRowClick ? 'pointer' : 'default',
                  background: expandedRow === (row.id || row.agent_id) ? 'rgba(124,58,237,0.10)' : 'rgba(13,13,21,0.36)',
                  transition: 'background 0.12s ease, box-shadow 0.12s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(124,58,237,0.10)';
                  e.currentTarget.style.boxShadow = 'inset 3px 0 0 rgba(6,182,212,0.65)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = expandedRow === (row.id || row.agent_id) ? 'rgba(124,58,237,0.10)' : 'rgba(13,13,21,0.36)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                {columns.map((col) => (
                  <td key={col.key} style={{
                    padding: '12px 16px',
                    color: col.muted ? '#73738c' : '#d7d7e6',
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
                <tr style={{ background: 'rgba(8,8,14,0.94)' }}>
                  <td colSpan={columns.length} style={{ padding: 0 }}>
                    {renderExpanded(row)}
                  </td>
                </tr>
              )}
            </Fragment>
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
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'rgba(2,2,8,0.78)',
        backdropFilter: 'blur(10px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: 'linear-gradient(180deg, #111118, #0a0a0f)',
        border: '1px solid rgba(124,58,237,0.38)',
        borderRadius: '16px',
        width,
        maxWidth: '95vw',
        maxHeight: '90vh',
        overflow: 'auto',
        boxShadow: '0 0 30px rgba(124,58,237,0.18), 0 28px 80px rgba(0,0,0,0.72)',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '19px 22px',
          borderBottom: '1px solid rgba(124,58,237,0.22)',
        }}>
          <h2 style={{ fontSize: '14px', fontWeight: '800', color: '#fff', letterSpacing: '0.1em', textTransform: 'uppercase' }}>{title}</h2>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#8b8ba4', cursor: 'pointer', padding: '2px', lineHeight: 1 }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
      {label && <label style={{ fontSize: '11px', fontWeight: '800', color: '#9ca3c7', letterSpacing: '0.1em', textTransform: 'uppercase' }}>{label}</label>}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          background: '#090911',
          border: `1px solid ${error ? '#ef4444' : 'rgba(124,58,237,0.30)'}`,
          borderRadius: '9px',
          padding: '10px 12px',
          color: '#f5f5ff',
          fontSize: '13px',
          fontFamily: 'inherit',
          outline: 'none',
          width: '100%',
          transition: 'border-color 0.14s, box-shadow 0.14s',
        }}
        onFocus={(e) => {
          e.target.style.borderColor = theme.cyan;
          e.target.style.boxShadow = '0 0 16px rgba(6,182,212,0.16)';
        }}
        onBlur={(e) => {
          e.target.style.borderColor = error ? '#ef4444' : 'rgba(124,58,237,0.30)';
          e.target.style.boxShadow = 'none';
        }}
      />
      {error && <span style={{ fontSize: '11px', color: '#fb7185' }}>{error}</span>}
    </div>
  );
}

export function EmptyState({ icon, title, description }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '70px 24px',
      gap: '13px',
      border: '1px solid rgba(124,58,237,0.20)',
      borderRadius: '16px',
      background: 'rgba(17,17,24,0.56)',
    }}>
      <div style={{ color: '#7c3aed', marginBottom: '4px', filter: 'drop-shadow(0 0 16px rgba(124,58,237,0.5))' }}>{icon}</div>
      <div style={{ fontSize: '15px', fontWeight: '800', color: '#f5f5ff', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{title}</div>
      {description && <div style={{ fontSize: '13px', color: '#73738c', textAlign: 'center', maxWidth: '340px' }}>{description}</div>}
    </div>
  );
}
