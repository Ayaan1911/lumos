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
      background: '#111118', border: '1px solid rgba(124,58,237,0.35)',
      borderRadius: '10px', padding: '9px 12px', fontSize: '12px',
      boxShadow: '0 0 20px rgba(124,58,237,0.18)',
    }}>
      <div style={{ color: '#9ca3c7', marginBottom: '4px', fontFamily: 'JetBrains Mono, monospace' }}>{label}</div>
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
        flex: 1, height: '6px', background: '#171724',
        borderRadius: '3px', overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: c, borderRadius: '3px', boxShadow: `0 0 12px ${c}88`,
          transition: 'width 0.4s ease',
        }} />
      </div>
      <span style={{
        fontSize: '11px', color: danger ? '#fb7185' : warning ? '#fbbf24' : '#73738c',
        width: '36px', textAlign: 'right', flexShrink: 0,
      }}>
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

// ── Colors ────────────────────────────────────────────────────────────────────
const PALETTE = ['#7c3aed', '#06b6d4', '#8b5cf6', '#22c55e', '#f59e0b', '#ef4444', '#38bdf8'];

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
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '14px', marginBottom: '28px' }}>
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
              accentColor="#06b6d4"
            />
            <StatCard
              icon={<Award size={16} />}
              label="Top Agent by Usage"
              value={topAgent?.agent_id && topAgent.agent_id.length > 14
                ? topAgent.agent_id.slice(0, 14) + '…'
                : topAgent?.agent_id || '—'}
              sub={topAgent ? `${topAgent.usage?.toLocaleString()} units · ${topAgent.period}` : 'none'}
              accentColor="#22c55e"
            />
          </div>

          {/* ── Bar Chart ── */}
          <div style={{
            background: 'linear-gradient(180deg, rgba(17,17,24,0.96), rgba(10,10,15,0.96))', border: '1px solid rgba(124,58,237,0.22)', borderRadius: '14px',
            padding: '22px 24px', marginBottom: '24px',
            boxShadow: '0 18px 44px rgba(0,0,0,0.28)',
          }}>
            <div style={{ marginBottom: '16px', fontSize: '12px', fontWeight: '800', color: '#e5e7ff', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              Usage by Agent
            </div>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 4, right: 0, left: -12, bottom: 0 }}>
                  <XAxis
                    dataKey="name"
                    tick={{ fill: '#73738c', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}
                    axisLine={false} tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#62627a', fontSize: 11 }}
                    axisLine={false} tickLine={false}
                  />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: '#7c3aed12' }} />
                  <Bar dataKey="usage" radius={[3, 3, 0, 0]} maxBarSize={48}>
                    {chartData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
            <div style={{ height: '120px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#62627a', fontSize: '13px' }}>
                No chart data
              </div>
            )}
          </div>

          {/* ── Detailed Table ── */}
          <div style={{ background: '#111118', border: '1px solid rgba(124,58,237,0.22)', borderRadius: '14px', overflow: 'hidden', boxShadow: '0 18px 44px rgba(0,0,0,0.28)' }}>
            <div style={{ padding: '15px 20px', borderBottom: '1px solid rgba(124,58,237,0.18)', fontSize: '12px', fontWeight: '800', color: '#e5e7ff', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              Budget Details
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#07070c', borderBottom: '1px solid rgba(124,58,237,0.18)' }}>
                  {['Agent', 'Period', 'Usage', 'Limit', 'Budget Used'].map((h) => (
                    <th key={h} style={{
                      padding: '9px 16px', textAlign: 'left',
                      fontSize: '10px', fontWeight: '800', color: '#8b8ba4',
                      letterSpacing: '0.12em', textTransform: 'uppercase',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {agents.map((a, i) => (
                  <tr
                    key={`${a.agent_id}-${a.period}`}
                    style={{ borderBottom: '1px solid rgba(35,35,58,0.58)' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(124,58,237,0.10)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                  >
                    <td style={{ padding: '12px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: '#c4b5fd' }}>
                      {a.agent_id}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{
                        fontSize: '11px', fontWeight: '800', color: '#06b6d4',
                        background: '#06b6d418', border: '1px solid #06b6d440',
                        padding: '3px 8px', borderRadius: '999px',
                      }}>
                        {a.period}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '13px', color: '#e5e7ff', fontWeight: '700' }}>
                      {(a.usage || 0).toLocaleString()}
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '13px', color: a.limit ? '#9ca3c7' : '#3a3a52' }}>
                      {a.limit ? a.limit.toLocaleString() : '∞'}
                    </td>
                    <td style={{ padding: '12px 16px', width: '200px' }}>
                      {a.limit ? (
                        <ProgressBar value={a.usage || 0} max={a.limit} color={PALETTE[i % PALETTE.length]} />
                      ) : (
                        <span style={{ fontSize: '11px', color: '#3a3a52' }}>No limit set</span>
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
            background: '#111118',
            border: '1px solid rgba(6,182,212,0.18)',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '12px',
            color: '#73738c',
          }}>
            <AlertCircle size={13} color="#06b6d4" />
            Budget limits are configured in your policy YAML under the <code style={{ fontFamily: 'JetBrains Mono, monospace', color: '#06b6d4' }}>budgets:</code> key. Periods reset daily or monthly.
          </div>
        </>
      )}
    </div>
  );
}
