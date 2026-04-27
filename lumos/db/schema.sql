CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS agents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT UNIQUE NOT NULL,
  display_name TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at TIMESTAMPTZ,
  CONSTRAINT agents_status_check CHECK (status IN ('active', 'revoked'))
);

CREATE TABLE IF NOT EXISTS agent_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
  kid TEXT NOT NULL,
  public_key TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at TIMESTAMPTZ,
  UNIQUE(agent_id, kid),
  CONSTRAINT agent_keys_status_check CHECK (status IN ('active', 'revoked'))
);

CREATE TABLE IF NOT EXISTS sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT UNIQUE NOT NULL,
  agent_id TEXT NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
  kid TEXT NOT NULL,
  parent_session_id TEXT REFERENCES sessions(session_id),
  issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  revoked_at TIMESTAMPTZ,
  CONSTRAINT sessions_status_check CHECK (status IN ('active', 'expired', 'revoked')),
  CONSTRAINT sessions_expiry_check CHECK (expires_at > issued_at),
  CONSTRAINT sessions_agent_key_fk FOREIGN KEY (agent_id, kid) REFERENCES agent_keys(agent_id, kid)
);

CREATE TABLE IF NOT EXISTS auth_nonces (
  nonce TEXT PRIMARY KEY,
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ
);

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS kid TEXT;
ALTER TABLE sessions ALTER COLUMN kid SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'sessions_agent_key_fk'
  ) THEN
    ALTER TABLE sessions
      ADD CONSTRAINT sessions_agent_key_fk
      FOREIGN KEY (agent_id, kid) REFERENCES agent_keys(agent_id, kid);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS capabilities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  capability_id TEXT UNIQUE NOT NULL,
  session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  agent_id TEXT NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
  audience TEXT NOT NULL,
  tools JSONB NOT NULL,
  constraints JSONB NOT NULL DEFAULT '{}'::jsonb,
  issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  revoked_at TIMESTAMPTZ,
  CONSTRAINT capabilities_status_check CHECK (status IN ('active', 'expired', 'revoked')),
  CONSTRAINT capabilities_expiry_check CHECK (expires_at > issued_at),
  CONSTRAINT capabilities_tools_array_check CHECK (jsonb_typeof(tools) = 'array'),
  CONSTRAINT capabilities_constraints_object_check CHECK (jsonb_typeof(constraints) = 'object')
);

CREATE TABLE IF NOT EXISTS audit_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  event_type TEXT NOT NULL,
  agent_id TEXT REFERENCES agents(agent_id) ON DELETE SET NULL,
  session_id TEXT REFERENCES sessions(session_id) ON DELETE SET NULL,
  capability_id TEXT REFERENCES capabilities(capability_id) ON DELETE SET NULL,
  audience TEXT,
  tool_name TEXT,
  decision TEXT NOT NULL,
  reason TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT audit_events_decision_check CHECK (decision IN ('allow', 'deny', 'issue', 'revoke', 'error')),
  CONSTRAINT audit_events_metadata_object_check CHECK (jsonb_typeof(metadata) = 'object')
);

ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS event_hash TEXT;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS prev_hash TEXT;

CREATE TABLE IF NOT EXISTS rate_limit_state (
  agent_id TEXT NOT NULL,
  tool TEXT NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  call_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (agent_id, tool),
  CONSTRAINT rate_limit_state_call_count_check CHECK (call_count >= 0)
);

CREATE TABLE IF NOT EXISTS budget_state (
  agent_id TEXT NOT NULL,
  period TEXT NOT NULL,
  usage INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (agent_id, period),
  CONSTRAINT budget_state_usage_check CHECK (usage >= 0)
);

CREATE INDEX IF NOT EXISTS idx_agent_keys_agent_id ON agent_keys(agent_id);
CREATE INDEX IF NOT EXISTS idx_sessions_agent_id ON sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_sessions_kid ON sessions(kid);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_auth_nonces_expires_at ON auth_nonces(expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_nonces_consumed_at ON auth_nonces(consumed_at);
CREATE INDEX IF NOT EXISTS idx_capabilities_session_id ON capabilities(session_id);
CREATE INDEX IF NOT EXISTS idx_capabilities_agent_id ON capabilities(agent_id);
CREATE INDEX IF NOT EXISTS idx_capabilities_audience ON capabilities(audience);
CREATE INDEX IF NOT EXISTS idx_capabilities_status ON capabilities(status);
CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_agent_id ON audit_events(agent_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_session_id ON audit_events(session_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_rate_limit_state_window ON rate_limit_state(window_start);
CREATE INDEX IF NOT EXISTS idx_budget_state_agent_period ON budget_state(agent_id, period);

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;
ALTER TABLE capabilities ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;
