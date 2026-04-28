import client from './client';

export const getEvents = (params = {}) =>
  client.get('/api/events', { params }).then((r) => r.data);

export const getEventById = (id) =>
  client.get(`/api/events/${id}`).then((r) => r.data);

export const verifyAuditChain = (params = {}) =>
  client.get('/api/audit/verify', { params }).then((r) => r.data);
