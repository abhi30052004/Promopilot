export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function resolveMediaUrl(value) {
  if (!value) return null;
  if (/^https?:\/\//i.test(value)) return value;
  if (value.startsWith('/api/') || value.startsWith('/media/')) {
    return `${API_BASE_URL}${value}`;
  }
  return `${API_BASE_URL}/media/${value.replace(/^\/+/, '')}`;
}

export function contentMediaUrl(item) {
  return resolveMediaUrl(item?.media_url || item?.image_path);
}
