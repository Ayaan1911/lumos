import client from './client';

export const getPolicy = () =>
  client.get('/api/policy').then((r) => r.data);

export const updatePolicy = (yamlContent) =>
  client.put('/api/policy', { yaml_content: yamlContent }).then((r) => r.data);

export const validatePolicy = (yamlContent) =>
  client.post('/api/policy/validate', { yaml_content: yamlContent }).then((r) => r.data);
