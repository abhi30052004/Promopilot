import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
});

// Global in-flight request counter (drives the top progress bar).
let inflight = 0;
const listeners = new Set();
const notify = () => listeners.forEach((fn) => fn(inflight > 0));
export function subscribeLoading(fn) {
  listeners.add(fn);
  fn(inflight > 0);
  return () => listeners.delete(fn);
}

api.interceptors.request.use((config) => {
  inflight += 1;
  notify();
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    inflight = Math.max(0, inflight - 1);
    notify();
    return response;
  },
  (error) => {
    inflight = Math.max(0, inflight - 1);
    notify();
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
