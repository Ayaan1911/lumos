import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:4001',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.request.use((config) => {
  const token = import.meta.env.VITE_ADMIN_TOKEN;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const message = err.response?.data?.detail || err.response?.data?.error || err.message || 'Unknown error';
    return Promise.reject(new Error(message));
  }
);

export default client;
