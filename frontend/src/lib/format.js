export const PLATFORMS = ['instagram', 'facebook', 'linkedin', 'tiktok', 'x', 'telegram'];
export const DEFAULT_PLATFORMS = ['instagram', 'facebook', 'linkedin'];
export const APP_TIMEZONE = 'Asia/Jerusalem';

// The API returns naive UTC timestamps (no "Z"); make that explicit before parsing.
export function parseApiDate(value) {
  if (!value) return null;
  const text = String(value);
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(text);
  const date = new Date(hasZone ? text : `${text}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function fmtDateTime(value, lang = 'en') {
  const date = parseApiDate(value);
  if (!date) return '—';
  return new Intl.DateTimeFormat(lang === 'he' ? 'he-IL' : 'en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: APP_TIMEZONE,
  }).format(date);
}

export function fmtDate(value, lang = 'en') {
  const date = parseApiDate(value);
  if (!date) return '—';
  return new Intl.DateTimeFormat(lang === 'he' ? 'he-IL' : 'en-GB', {
    dateStyle: 'medium',
    timeZone: APP_TIMEZONE,
  }).format(date);
}

// YYYY-MM-DD of "now + days" in the app timezone (for <input type="date"> defaults).
export function dateInputValue(daysAhead = 0) {
  const date = new Date(Date.now() + daysAhead * 86400000);
  return new Intl.DateTimeFormat('en-CA', { timeZone: APP_TIMEZONE }).format(date);
}

export function errorText(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ');
  return error?.message || fallback;
}

export const statusTone = {
  PENDING: 'bg-amber-100 text-amber-800',
  APPROVED: 'bg-emerald-100 text-emerald-800',
  REJECTED: 'bg-rose-100 text-rose-800',
  DRAFT: 'bg-slate-100 text-slate-700',
  SCHEDULED: 'bg-violet-100 text-violet-800',
  PUBLISHED: 'bg-emerald-100 text-emerald-800',
  FAILED: 'bg-red-100 text-red-800',
  COMPLETED: 'bg-emerald-100 text-emerald-800',
  GENERATING: 'bg-sky-100 text-sky-800',
  PROCESSING: 'bg-sky-100 text-sky-800',
  SUCCESS: 'bg-emerald-100 text-emerald-800',
  NONE: 'bg-slate-100 text-slate-600',
  STARTED: 'bg-sky-100 text-sky-800',
  SKIPPED: 'bg-slate-100 text-slate-600',
};

// "2 minutes ago" / "לפני 2 דקות" (localized, based on the API's UTC timestamps)
export function timeAgo(value, lang = 'en') {
  const date = parseApiDate(value);
  if (!date) return '';
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(lang === 'he' ? 'he' : 'en', { numeric: 'auto' });
  const abs = Math.abs(seconds);
  if (abs < 45) return rtf.format(0, 'second');
  if (abs < 3600) return rtf.format(Math.round(seconds / 60), 'minute');
  if (abs < 86400) return rtf.format(Math.round(seconds / 3600), 'hour');
  return rtf.format(Math.round(seconds / 86400), 'day');
}
