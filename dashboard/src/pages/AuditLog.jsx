import { useState, useEffect, useCallback, useRef } from 'react';
import { ShieldCheck, ShieldX, Filter, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
import { getEvents, verifyAuditChain } from '../api/audit';
import { Badge } from '../components/Badge';
import { toast } from '../components/Toast';
import { PageHeader, Table, Button, Spinner } from '../components/Layout';

function fmtTime(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false, year: 'numeric',
  });
}

const PAGE_SIZE = 50;

export default function AuditLog() {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);

  // Filters
  const [agentFilter, setAgentFilter] = useState('');
  const [decisionFilter, setDecisionFilter] = useState('');
  const [toolFilter, setToolFilter] = useState('');
  const agentRef = useRef('');
  const decisionRef = useRef('');
  const toolRef = useRef('');

  const load = useCallback(async (pg = 0) => {
    setLoading(true);
    try {
      const params = {
        limit: PAGE_SIZE,
        offset: pg * PAGE_SIZE,
        ...(agentFilter && { agent_id: agentFilter }),
        ...(decisionFilter && { decision: decisionFilter }),
        ...(toolFilter && { tool_name: toolFilter }),
      };
      const data = await getEvents(params);
      setEvents(data.events || []);
      setTotal(data.total || 0);
      setLastRefresh(new Date());
    } catch (err) {
      toast.error(`Failed to load audit events: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [agentFilter, decisionFilter, toolFilter]);

  useEffect(() => { load(page); }, [load, page]);

  useEffect(() => {
    const id = setInterval(() => load(page), 15_000);
    return () => clearInterval(id);
  }, [load, page]);

  const handleFilter = () => {
    setAgentFilter(agentRef.current.value.trim());
    setDecisionFilter(decisionRef.current.value);
    setToolFilter(toolRef.current.value.trim());
    setPage(0);
  };

  const clearFilters = () => {
    agentRef.current.value = '';
    decisionRef.current.value = '';
    toolRef.current.value = '';
    setAgentFilter('');
    setDecisionFilter('');
    setToolFilter('');
    setPage(0);
  };

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const res = await verifyAuditChain({ limit: 5000 });
      if (res.valid) {
        toast.success(`Merkle chain verified — ${res.events_checked} events checked ✓`);
      } else {
        toast.error(`Chain integrity FAILED: ${res.reason}`);
      }
    } catch (err) {
      toast.error(`Verification failed: ${err.message}`);
    } finally {
      setVerifying(false);
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const COLS = [
    {
      key: 'timestamp', label: 'Time',
      render: (r) => <span style={{ color: '#666', fontSize: '11.5px', fontFamily: 'JetBrains Mono, monospace' }}>{fmtTime(r.timestamp)}</span>,
      width: '190px',
    },
    {
      key: 'agent_id', label: 'Agent',
      render: (r) => (
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11.5px', color: '#999' }}>
          {r.agent_id || <span style={{ color: '#333' }}>—</span>}
        </span>
      ),
      width: '160px',
    },
    {
      key: 'event_type', label: 'Type',
      render: (r) => <span style={{ color: '#666', fontSize: '12px' }}>{r.event_type}</span>,
      width: '140px',
    },
    {
      key: 'tool_name', label: 'Tool',
      render: (r) => <span style={{ color: '#ccc', fontSize: '12px' }}>{r.tool_name || <span style={{ color: '#333' }}>—</span>}</span>,
    },
    {
      key: 'decision', label: 'Decision',
      render: (r) => <Badge type={r.decision} />,
      width: '90px',
    },
    {
      key: 'reason', label: 'Reason',
      render: (r) => <span style={{ color: '#555', fontSize: '12px' }}>{r.reason || '—'}</span>,
      wrap: true,
    },
    {
      key: 'event_hash', label: 'Hash',
      render: (r) => r.event_hash ? (
        <span style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: '10px',
          color: '#444',
          letterSpacing: '0.02em',
        }} title={r.event_hash}>
          {r.event_hash.slice(0, 12)}…
        </span>
      ) : <span style={{ color: '#2a2a2a' }}>—</span>,
      width: '100px',
    },
  ];

  return (
    <div>
      <PageHeader
        title="Audit Log"
        description="Tamper-evident record of all enforcement decisions"
        action={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button variant="secondary" onClick={() => load(page)}>
              <RefreshCw size={13} /> Refresh
            </Button>
            <Button onClick={handleVerify} loading={verifying}>
              <ShieldCheck size={13} /> Verify Chain
            </Button>
          </div>
        }
      />

      {/* ── Filter Bar ── */}
      <div style={{
        display: 'flex', gap: '8px', marginBottom: '16px',
        padding: '12px 14px',
        background: '#111', border: '1px solid #1f1f1f', borderRadius: '8px',
        alignItems: 'center', flexWrap: 'wrap',
      }}>
        <Filter size={13} color="#555" />
        <input
          ref={agentRef}
          placeholder="Filter by agent ID…"
          style={filterInputStyle}
          onKeyDown={(e) => e.key === 'Enter' && handleFilter()}
          defaultValue={agentFilter}
        />
        <select ref={decisionRef} defaultValue={decisionFilter} style={filterSelectStyle}>
          <option value="">All decisions</option>
          <option value="allow">allow</option>
          <option value="deny">deny</option>
          <option value="issue">issue</option>
          <option value="revoke">revoke</option>
          <option value="error">error</option>
        </select>
        <input
          ref={toolRef}
          placeholder="Filter by tool…"
          style={filterInputStyle}
          onKeyDown={(e) => e.key === 'Enter' && handleFilter()}
          defaultValue={toolFilter}
        />
        <Button size="sm" onClick={handleFilter}>Apply</Button>
        {(agentFilter || decisionFilter || toolFilter) && (
          <Button size="sm" variant="ghost" onClick={clearFilters}>Clear</Button>
        )}
        <span style={{ marginLeft: 'auto', fontSize: '12px', color: '#444' }}>
          {!loading && `${total.toLocaleString()} total`}
          {lastRefresh && ` · refreshed ${lastRefresh.toLocaleTimeString()}`}
        </span>
      </div>

      {/* ── Table ── */}
      <Table
        columns={COLS}
        data={events}
        loading={loading}
        empty="No audit events found matching your filters"
      />

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px', justifyContent: 'flex-end' }}>
          <span style={{ fontSize: '12px', color: '#555' }}>
            Page {page + 1} of {totalPages}
          </span>
          <Button
            variant="secondary" size="sm"
            disabled={page === 0}
            onClick={() => setPage(p => Math.max(0, p - 1))}
          >
            <ChevronLeft size={14} />
          </Button>
          <Button
            variant="secondary" size="sm"
            disabled={page >= totalPages - 1}
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
          >
            <ChevronRight size={14} />
          </Button>
        </div>
      )}
    </div>
  );
}

const filterInputStyle = {
  background: '#0a0a0a',
  border: '1px solid #222',
  borderRadius: '5px',
  padding: '5px 10px',
  color: '#ccc',
  fontSize: '12px',
  fontFamily: 'inherit',
  outline: 'none',
  width: '180px',
};

const filterSelectStyle = {
  background: '#0a0a0a',
  border: '1px solid #222',
  borderRadius: '5px',
  padding: '5px 10px',
  color: '#ccc',
  fontSize: '12px',
  fontFamily: 'inherit',
  outline: 'none',
  cursor: 'pointer',
};
