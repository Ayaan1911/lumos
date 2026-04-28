import client from './client';

export const getSummary = () =>
  client.get('/api/stats/summary').then((r) => r.data);

export const getCosts = () =>
  client.get('/api/stats/costs').then((r) => r.data);
