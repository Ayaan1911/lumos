import client from './client';

export const getAgents = (params = {}) =>
  client.get('/api/agents', { params }).then((r) => r.data);

export const getAgentById = (agentId) =>
  client.get(`/api/agents/${agentId}`).then((r) => r.data);

export const createAgent = (data) =>
  client.post('/v1/agents', data).then((r) => r.data);

export const revokeAgent = (agentId) =>
  client.post(`/v1/agents/${agentId}/revoke`).then((r) => r.data);

export const createAgentKey = (agentId, data) =>
  client.post(`/v1/agents/${agentId}/keys`, data).then((r) => r.data);
