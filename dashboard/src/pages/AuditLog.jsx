import { useState, useEffect, useCallback, useRef } from 'react';
import { ShieldCheck, Filter, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
import { getEvents, verifyAuditChain } from '../api/audit';
import { Badge } from '../components/Badge';
import { toast } from '../components/Toast';
import { PageHeader, Table, Button } from '../components/Layout';

function fmtTime(ts) {
  if (!ts) return '-';
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
        toast.success(`Merkle chain verified - ${res.events_checked} events checked`);
      } else {
        toast.error(`Chain integrity failed: ${res.reason}`);
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
      render: (r) => <span style={{ color: '#73738c', fontSize: '11.5px', fontFamily: 'JetBrains Mono, monospace' }}>{fmtTime(r.timestamp)}</span>,
      width: '190px',
    },
    {
      key: 'agent_id', label: 'Agent',
      render: (r) => (
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11.5px', color: '#c4b5fd' }}>
          {r.agent_id || <span style={{ color: '#3a3a52' }}>-</span>}
        </span>
      ),
      width: '160px',
    },
    {
      key: 'event_type', label: 'Type',
      render: (r) => <span style={{ color: '#06b6d4', fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em' }}>{r.event_type}</span>,
      width: '140px',
    },
    {
      key: 'tool_name', label: 'Tool',
      render: (r) => <span style={{ color: '#e5e7ff', fontSize: '12px' }}>{r.tool_name || <span style={{ color: '#3a3a52' }}>-</span>}</span>,
    },
    {
      key: 'decision', label: 'Decision',
      render: (r) => <Badge type={r.decision} />,
      width: '90px',
    },
    {
      key: 'reason', label: 'Reason',
      render: (r) => <span style={{ color: '#73738c', fontSize: '12px' }}>{r.reason || '-'}</span>,
      wrap: true,
    },
    {
      key: 'event_hash', label: 'Hash',
      render: (r) => r.event_hash ? (
        <span style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: '10px',
          color: '#62627a',
          letterSpacing: '0.02em',
        }} title={r.event_hash}>
          {r.event_hash.slice(0, 12)}...
        </span>
      ) : <span style={{ color: '#3a3a52' }}>-</span>,
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

      <div style={{
        display: 'flex', gap: '8px', marginBottom: '16px',
        padding: '13px 14px',
        background: 'linear-gradient(180deg, rgba(17,17,24,0.94), rgba(10,10,15,0.94))',
        border: '1px solid rgba(124,58,237,0.22)',
        borderRadius: '14px',
        boxShadow: '0 18px 44px rgba(0,0,0,0.24)',
        alignItems: 'center', flexWrap: 'wrap',
      }}>
        <Filter size={13} color="#06b6d4" />
        <input
          ref={agentRef}
          placeholder="Filter by agent ID..."
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
          placeholder="Filter by tool..."
          style={filterInputStyle}
          onKeyDown={(e) => e.key === 'Enter' && handleFilter()}
          defaultValue={toolFilter}
        />
        <Button size="sm" onClick={handleFilter}>Apply</Button>
        {(agentFilter || decisionFilter || toolFilter) && (
          <Button size="sm" variant="ghost" onClick={clearFilters}>Clear</Button>
        )}
        <span style={{ marginLeft: 'auto', fontSize: '12px', color: '#73738c', fontFamily: 'JetBrains Mono, monospace' }}>
          {!loading && `${total.toLocaleString()} total`}
          {lastRefresh && ` / refreshed ${lastRefresh.toLocaleTimeString()}`}
        </span>
      </div>

      <Table
        columns={COLS}
        data={events}
        loading={loading}
        empty="No audit events found matching your filters"
      />

      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px', justifyContent: 'flex-end' }}>
          <span style={{ fontSize: '12px', color: '#73738c', fontFamily: 'JetBrains Mono, monospace' }}>
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
  background: '#090911',
  border: '1px solid rgba(124,58,237,0.30)',
  borderRadius: '8px',
  padding: '7px 10px',
  color: '#e5e7ff',
  fontSize: '12px',
  fontFamily: 'inherit',
  outline: 'none',
  width: '180px',
};

const filterSelectStyle = {
  background: '#090911',
  border: '1px solid rgba(124,58,237,0.30)',
  borderRadius: '8px',
  padding: '7px 10px',
  color: '#e5e7ff',
  fontSize: '12px',
  fontFamily: 'inherit',
  outline: 'none',
  cursor: 'pointer',
};
