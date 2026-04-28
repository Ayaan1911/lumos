import { useState, useEffect, useCallback } from 'react';
import { Activity, Users, ShieldCheck, ShieldX, RefreshCw } from 'lucide-react';
import { getSummary } from '../api/stats';
import { getEvents } from '../api/audit';
import { StatCard } from '../components/StatCard';
import { Badge } from '../components/Badge';
import { PageHeader, Table, Spinner } from '../components/Layout';

function fmtTime(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
}

function fmtPct(val) {
  if (val == null || isNaN(val)) return '—';
  return `${(val * 100).toFixed(1)}%`;
}

const EVENT_COLS = [
  { key: 'timestamp',  label: 'Time',     render: (r) => <span style={{ color: '#666', fontSize: '12px', fontFamily: 'JetBrains Mono, monospace' }}>{fmtTime(r.timestamp)}</span> },
  { key: 'agent_id',   label: 'Agent',    render: (r) => <span style={{ color: '#aaa', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}>{r.agent_id || '—'}</span> },
  { key: 'tool_name',  label: 'Tool',     render: (r) => <span style={{ color: '#ccc' }}>{r.tool_name || <span style={{ color: '#333' }}>—</span>}</span> },
  { key: 'decision',   label: 'Decision', render: (r) => <Badge type={r.decision} />, width: '90px' },
  { key: 'reason',     label: 'Reason',   render: (r) => <span style={{ color: '#555', fontSize: '12px' }}>{r.reason || '—'}</span>, wrap: true },
];

export default function Overview() {
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);

  const load = useCallback(async () => {
    try {
      const [sum, evs] = await Promise.all([
        getSummary(),
        getEvents({ limit: 10, offset: 0 }),
      ]);
      setSummary(sum);
      setEvents(evs.events || []);
      setLastRefresh(new Date());
    } catch {
      // silently fail in background refreshes
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, [load]);

  const allowRate = summary?.total_events > 0
    ? ((summary.allowed_events / summary.total_events) * 100).toFixed(1)
    : null;
  const denyRate = summary?.total_events > 0
    ? ((summary.denied_events / summary.total_events) * 100).toFixed(1)
    : null;

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Real-time stats and recent activity across all MCP agents"
        action={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#444', fontSize: '12px' }}>
            <RefreshCw size={12} />
            {lastRefresh ? `Refreshed ${lastRefresh.toLocaleTimeString()}` : 'Loading…'}
          </div>
        }
      />

      {/* ── Stat Cards ── */}
      {loading && !summary ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '60px' }}>
          <Spinner size={28} />
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', gap: '12px', marginBottom: '28px' }}>
            <StatCard
              icon={<Users size={16} />}
              label="Total Agents"
              value={summary?.total_agents ?? '—'}
              sub={`${summary?.active_agents ?? 0} active`}
              accentColor="#7c3aed"
            />
            <StatCard
              icon={<Activity size={16} />}
              label="Total Events"
              value={summary?.total_events?.toLocaleString() ?? '—'}
              sub="all time"
              accentColor="#888"
            />
            <StatCard
              icon={<ShieldCheck size={16} />}
              label="Allow Rate"
              value={allowRate != null ? `${allowRate}%` : '—'}
              sub={`${summary?.allowed_events ?? 0} allowed`}
              accentColor="#22c55e"
            />
            <StatCard
              icon={<ShieldX size={16} />}
              label="Block Rate"
              value={denyRate != null ? `${denyRate}%` : '—'}
              sub={`${summary?.denied_events ?? 0} denied`}
              accentColor="#ef4444"
            />
          </div>

          {/* ── Audit Chain Status ── */}
          {summary?.audit_chain_verified != null && (
            <div style={{
              marginBottom: '24px',
              padding: '10px 14px',
              borderRadius: '6px',
              background: summary.audit_chain_verified ? '#22c55e10' : '#ef444410',
              border: `1px solid ${summary.audit_chain_verified ? '#22c55e30' : '#ef444430'}`,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: summary.audit_chain_verified ? '#22c55e' : '#ef4444',
            }}>
              {summary.audit_chain_verified
                ? <><ShieldCheck size={13} /> Merkle audit chain verified</>
                : <><ShieldX size={13} /> Audit chain integrity check FAILED — investigate immediately</>
              }
            </div>
          )}

          {/* ── Recent Events ── */}
          <div>
            <div style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '13px', fontWeight: '500', color: '#888' }}>Recent Events</span>
              <span style={{ fontSize: '11px', color: '#444' }}>Auto-refreshes every 10s</span>
            </div>
            <Table
              columns={EVENT_COLS}
              data={events}
              loading={loading && events.length === 0}
              empty="No events recorded yet"
            />
          </div>
        </>
      )}
    </div>
  );
}
