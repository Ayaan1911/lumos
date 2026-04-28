import { useState, useEffect, useCallback } from 'react';
import { DollarSign, TrendingUp, Award, AlertCircle } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { getCosts } from '../api/stats';
import { toast } from '../components/Toast';
import { StatCard } from '../components/StatCard';
import { PageHeader, Spinner, EmptyState } from '../components/Layout';

// ── Custom Tooltip for Recharts ─────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#1a1a1a', border: '1px solid #2a2a2a',
      borderRadius: '6px', padding: '8px 12px', fontSize: '12px',
    }}>
      <div style={{ color: '#888', marginBottom: '4px' }}>{label}</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.fill || '#7c3aed', fontWeight: '500' }}>
          {p.name}: <span style={{ color: '#fff' }}>{p.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

// ── Progress Bar ────────────────────────────────────────────────────────────────
function ProgressBar({ value, max, color }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const danger = pct >= 90;
  const warning = pct >= 70;
  const c = danger ? '#ef4444' : warning ? '#f59e0b' : color || '#7c3aed';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <div style={{
        flex: 1, height: '5px', background: '#1a1a1a',
        borderRadius: '3px', overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: c, borderRadius: '3px',
          transition: 'width 0.4s ease',
        }} />
      </div>
      <span style={{
        fontSize: '11px', color: danger ? '#ef4444' : warning ? '#f59e0b' : '#666',
        width: '36px', textAlign: 'right', flexShrink: 0,
      }}>
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

// ── Colors ────────────────────────────────────────────────────────────────────
const PALETTE = ['#7c3aed', '#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#4f46e5', '#4338ca'];

// ── Costs Page ─────────────────────────────────────────────────────────────────
export default function Costs() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await getCosts();
      setAgents(data.agents || []);
    } catch (err) {
      toast.error(`Failed to load cost data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Derive summary stats
  const totalUsage = agents.reduce((s, a) => s + (a.usage || 0), 0);
  const topAgent = agents.length > 0
    ? agents.reduce((a, b) => ((a.usage || 0) > (b.usage || 0) ? a : b), agents[0])
    : null;

  // Chart data — one bar per agent per period
  const chartData = agents.map((a, i) => ({
    name: a.agent_id.length > 14 ? a.agent_id.slice(0, 14) + '…' : a.agent_id,
    fullName: a.agent_id,
    usage: a.usage || 0,
    period: a.period,
    color: PALETTE[i % PALETTE.length],
  }));

  if (loading) {
    return (
      <div>
        <PageHeader title="Costs" description="Agent budget usage and spend tracking" />
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '80px' }}>
          <Spinner size={28} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Costs"
        description="Agent budget usage and spend tracking"
      />

      {agents.length === 0 ? (
        <EmptyState
          icon={<DollarSign size={40} />}
          title="No budget data yet"
          description="Budget entries appear once agents start making tool calls. Configure budgets in the Policy editor."
        />
      ) : (
        <>
          {/* ── Summary Cards ── */}
          <div style={{ display: 'flex', gap: '12px', marginBottom: '28px' }}>
            <StatCard
              icon={<DollarSign size={16} />}
              label="Total Usage (all periods)"
              value={totalUsage.toLocaleString()}
              sub="aggregated call units"
              accentColor="#7c3aed"
            />
            <StatCard
              icon={<TrendingUp size={16} />}
              label="Active Budget Entries"
              value={agents.length}
              sub={`${new Set(agents.map(a => a.agent_id)).size} agents`}
              accentColor="#888"
            />
            <StatCard
              icon={<Award size={16} />}
              label="Top Agent by Usage"
              value={topAgent?.agent_id && topAgent.agent_id.length > 14
                ? topAgent.agent_id.slice(0, 14) + '…'
                : topAgent?.agent_id || '—'}
              sub={topAgent ? `${topAgent.usage?.toLocaleString()} units · ${topAgent.period}` : 'none'}
              accentColor="#f59e0b"
            />
          </div>

          {/* ── Bar Chart ── */}
          <div style={{
            background: '#111', border: '1px solid #1f1f1f', borderRadius: '8px',
            padding: '20px 24px', marginBottom: '24px',
          }}>
            <div style={{ marginBottom: '16px', fontSize: '13px', fontWeight: '500', color: '#888' }}>
              Usage by Agent
            </div>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 4, right: 0, left: -12, bottom: 0 }}>
                  <XAxis
                    dataKey="name"
                    tick={{ fill: '#555', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}
                    axisLine={false} tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#444', fontSize: 11 }}
                    axisLine={false} tickLine={false}
                  />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: '#ffffff08' }} />
                  <Bar dataKey="usage" radius={[3, 3, 0, 0]} maxBarSize={48}>
                    {chartData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: '120px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#333', fontSize: '13px' }}>
                No chart data
              </div>
            )}
          </div>

          {/* ── Detailed Table ── */}
          <div style={{ background: '#111', border: '1px solid #1f1f1f', borderRadius: '8px', overflow: 'hidden' }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid #1a1a1a', fontSize: '13px', fontWeight: '500', color: '#888' }}>
              Budget Details
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#0d0d0d', borderBottom: '1px solid #1a1a1a' }}>
                  {['Agent', 'Period', 'Usage', 'Limit', 'Budget Used'].map((h) => (
                    <th key={h} style={{
                      padding: '9px 16px', textAlign: 'left',
                      fontSize: '11px', fontWeight: '600', color: '#555',
                      letterSpacing: '0.05em', textTransform: 'uppercase',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {agents.map((a, i) => (
                  <tr
                    key={`${a.agent_id}-${a.period}`}
                    style={{ borderBottom: '1px solid #161616' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = '#141414'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                  >
                    <td style={{ padding: '12px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: '#ccc' }}>
                      {a.agent_id}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{
                        fontSize: '11px', fontWeight: '500', color: '#888',
                        background: '#1a1a1a', border: '1px solid #222',
                        padding: '2px 7px', borderRadius: '4px',
                      }}>
                        {a.period}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '13px', color: '#e5e5e5', fontWeight: '500' }}>
                      {(a.usage || 0).toLocaleString()}
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '13px', color: a.limit ? '#888' : '#333' }}>
                      {a.limit ? a.limit.toLocaleString() : '∞'}
                    </td>
                    <td style={{ padding: '12px 16px', width: '200px' }}>
                      {a.limit ? (
                        <ProgressBar value={a.usage || 0} max={a.limit} color={PALETTE[i % PALETTE.length]} />
                      ) : (
                        <span style={{ fontSize: '11px', color: '#333' }}>No limit set</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ── Budget Info ── */}
          <div style={{
            marginTop: '14px',
            padding: '10px 14px',
            background: '#111',
            border: '1px solid #1a1a1a',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '12px',
            color: '#444',
          }}>
            <AlertCircle size={13} />
            Budget limits are configured in your policy YAML under the <code style={{ fontFamily: 'JetBrains Mono, monospace', color: '#555' }}>budgets:</code> key. Periods reset daily or monthly.
          </div>
        </>
      )}
    </div>
  );
}
