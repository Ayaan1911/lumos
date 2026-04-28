import { useState, useEffect, useCallback } from 'react';
import { UserPlus, Users, ShieldOff, ChevronDown, ChevronUp, Key } from 'lucide-react';
import { getAgents, getAgentById, createAgent, revokeAgent } from '../api/agents';
import { Badge } from '../components/Badge';
import { toast } from '../components/Toast';
import { PageHeader, Table, Button, Modal, Input, Spinner, EmptyState } from '../components/Layout';

function fmtDate(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}

function fmtRelative(ts) {
  if (!ts) return 'Never';
  const diff = Date.now() - new Date(ts).getTime();
  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return `${Math.floor(diff / 86400000)}d ago`;
}

// ─── Register Agent Modal ──────────────────────────────────────────────────────
function RegisterModal({ open, onClose, onSuccess }) {
  const [fields, setFields] = useState({ agent_id: '', display_name: '' });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const set = (k) => (v) => setFields((f) => ({ ...f, [k]: v }));

  const validate = () => {
    const e = {};
    if (!fields.agent_id.trim()) e.agent_id = 'Agent ID is required';
    else if (!/^[a-z0-9_-]+$/i.test(fields.agent_id)) e.agent_id = 'Only letters, numbers, hyphens, underscores';
    if (!fields.display_name.trim()) e.display_name = 'Display name is required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async () => {
    if (!validate()) return;
    setLoading(true);
    try {
      await createAgent({ agent_id: fields.agent_id.trim(), display_name: fields.display_name.trim() });
      toast.success(`Agent "${fields.agent_id}" registered`);
      setFields({ agent_id: '', display_name: '' });
      setErrors({});
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(`Failed to register agent: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Register Agent">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ padding: '12px 13px', background: '#090911', border: '1px solid rgba(6,182,212,0.22)', borderRadius: '10px', fontSize: '12px', color: '#9ca3c7', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)' }}>
          Agents must authenticate with Ed25519 keys. Register here first, then add keys via API.
        </div>
        <Input label="Agent ID" value={fields.agent_id} onChange={set('agent_id')} placeholder="my-agent" error={errors.agent_id} />
        <Input label="Display Name" value={fields.display_name} onChange={set('display_name')} placeholder="My First Agent" error={errors.display_name} />
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '4px' }}>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} loading={loading}>Register Agent</Button>
        </div>
      </div>
    </Modal>
  );
}

// ─── Revoke Confirm Modal ──────────────────────────────────────────────────────
function RevokeModal({ open, agent, onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);

  const confirm = async () => {
    setLoading(true);
    try {
      await revokeAgent(agent.agent_id);
      toast.success(`Agent "${agent.agent_id}" revoked`);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(`Failed to revoke: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Revoke Agent" width="400px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ fontSize: '13px', color: '#aaa', lineHeight: '1.6' }}>
          Are you sure you want to revoke <strong style={{ color: '#fff' }}>{agent?.agent_id}</strong>?
          All active sessions and capabilities will be invalidated immediately. This cannot be undone.
        </div>
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" onClick={confirm} loading={loading}>
            <ShieldOff size={13} /> Revoke Agent
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// ─── Expanded Row: Agent Keys ──────────────────────────────────────────────────
function AgentExpanded({ agentId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAgentById(agentId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [agentId]);

  return (
    <div style={{ padding: '14px 16px 18px', borderTop: '1px solid rgba(124,58,237,0.20)', background: 'linear-gradient(180deg, rgba(10,10,18,0.96), rgba(7,7,12,0.96))' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '12px', color: '#06b6d4', fontSize: '11px', fontWeight: '800', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
        <Key size={11} /> Keys
      </div>
      {loading ? (
        <div style={{ padding: '16px 0' }}><Spinner size={16} /></div>
      ) : data?.keys?.length ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {data.keys.map((k) => (
            <div key={k.kid} style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '9px 12px', background: '#111118', border: '1px solid rgba(124,58,237,0.22)',
              borderRadius: '10px', fontSize: '12px',
            }}>
              <Badge type={k.status} />
              <span style={{ fontFamily: 'JetBrains Mono, monospace', color: '#c4b5fd', fontSize: '11px' }}>{k.kid}</span>
              <span style={{ color: '#62627a', fontSize: '11px', marginLeft: 'auto', fontFamily: 'JetBrains Mono, monospace' }}>
                {k.public_key?.slice(0, 40)}…
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: '12px', color: '#73738c' }}>No keys registered. Add one via the API.</div>
      )}
    </div>
  );
}

// ─── Agents Page ───────────────────────────────────────────────────────────────
export default function Agents() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [showRegister, setShowRegister] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await getAgents({ limit: 200 });
      setAgents(data.agents || []);
    } catch (err) {
      toast.error(`Failed to load agents: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const columns = [
    {
      key: 'agent_id', label: 'Agent ID',
      render: (r) => (
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: '#c4b5fd' }}>
          {r.agent_id}
        </span>
      ),
    },
    { key: 'display_name', label: 'Name', render: (r) => <span style={{ color: '#d7d7e6' }}>{r.display_name || '-'}</span> },
    {
      key: 'status', label: 'Status',
      render: (r) => <Badge type={r.status} />,
      width: '90px',
    },
    {
      key: 'stats.total_calls', label: 'Calls',
      render: (r) => <span style={{ color: '#06b6d4', fontFamily: 'JetBrains Mono, monospace' }}>{r.stats?.total_calls ?? 0}</span>,
      width: '80px',
    },
    {
      key: 'stats.last_seen', label: 'Last Seen',
      render: (r) => <span style={{ color: '#73738c', fontSize: '12px', fontFamily: 'JetBrains Mono, monospace' }}>{fmtRelative(r.stats?.last_seen)}</span>,
      width: '110px',
    },
    {
      key: 'created_at', label: 'Registered',
      render: (r) => <span style={{ color: '#73738c', fontSize: '12px', fontFamily: 'JetBrains Mono, monospace' }}>{fmtDate(r.created_at)}</span>,
      width: '130px',
    },
    {
      key: 'actions', label: '',
      render: (r) => (
        <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
          {r.status === 'active' && (
            <Button
              variant="danger" size="sm"
              onClick={(e) => { e.stopPropagation(); setRevokeTarget(r); }}
            >
              <ShieldOff size={12} /> Revoke
            </Button>
          )}
          <span style={{ color: '#7c3aed' }}>
            {expanded === r.agent_id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </span>
        </div>
      ),
      width: '140px',
    },
  ];

  const toggleExpand = (row) => {
    setExpanded((prev) => (prev === row.agent_id ? null : row.agent_id));
  };

  return (
    <div>
      <PageHeader
        title="Agents"
        description="Manage registered MCP agents and their cryptographic keys"
        action={
          <Button onClick={() => setShowRegister(true)}>
            <UserPlus size={14} /> Register Agent
          </Button>
        }
      />

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '80px' }}>
          <Spinner size={28} />
        </div>
      ) : agents.length === 0 ? (
        <EmptyState
          icon={<Users size={40} />}
          title="No agents registered yet"
          description="Register your first agent using the button above. Agents authenticate with Ed25519 keys."
        />
      ) : (
        <Table
          columns={columns}
          data={agents}
          loading={false}
          empty="No agents"
          onRowClick={toggleExpand}
          expandedRow={expanded}
          renderExpanded={(row) => <AgentExpanded agentId={row.agent_id} />}
        />
      )}

      <RegisterModal
        open={showRegister}
        onClose={() => setShowRegister(false)}
        onSuccess={load}
      />
      <RevokeModal
        open={!!revokeTarget}
        agent={revokeTarget}
        onClose={() => setRevokeTarget(null)}
        onSuccess={load}
      />
    </div>
  );
}
