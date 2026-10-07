import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, RefreshCw, RotateCw, X } from 'lucide-react';
import MediaPreview from '../components/MediaPreview';
import StatusBadge from '../components/StatusBadge';
import api from '../lib/api';
import { useLanguage } from '../lib/LanguageContext';
import { APP_TIMEZONE, PLATFORMS, errorText, fmtDateTime, parseApiDate } from '../lib/format';

const MAX_CHIPS = 3;
const pad = (n) => String(n).padStart(2, '0');
const ymd = (date) => `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
const utcDate = (y, m, d) => new Date(Date.UTC(y, m, d));

function localeOf(lang) {
  return lang === 'he' ? 'he-IL' : 'en-GB';
}

// YYYY-MM-DD of an API timestamp in the app timezone.
function dayKeyOf(value) {
  const date = parseApiDate(value);
  if (!date) return null;
  return new Intl.DateTimeFormat('en-CA', { timeZone: APP_TIMEZONE }).format(date);
}

function timeOf(value, lang) {
  const date = parseApiDate(value);
  if (!date) return '';
  return new Intl.DateTimeFormat(localeOf(lang), { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: APP_TIMEZONE }).format(date);
}

function chipTone(status) {
  return status === 'PUBLISHED'
    ? 'bg-emerald-100 text-emerald-900 hover:bg-emerald-200'
    : 'bg-violet-100 text-violet-900 hover:bg-violet-200';
}

function EventChip({ event, lang, t, onOpen }) {
  return (
    <button
      onClick={() => onOpen(event)}
      title={event.title || event.caption}
      className={`flex w-full items-center gap-1 truncate rounded px-1.5 py-0.5 text-start text-[11px] font-medium ${chipTone(event.status)}`}
    >
      <span className="shrink-0 font-bold">{t(`platform.${event.platform}`)}</span>
      <span className="shrink-0 opacity-70">{timeOf(event.event_at, lang)}</span>
      <span className="truncate">{event.title || event.property_name}</span>
    </button>
  );
}

function EventModal({ event, onClose, t, lang }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const isStory = event.kind === 'story';
  const timeLabel = event.status === 'PUBLISHED' ? t('calendar.d.published_at') : t('calendar.d.scheduled_at');
  const row = (label, value) => (value ? (
    <div className="flex flex-wrap gap-x-2 text-sm">
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd className="text-slate-900">{value}</dd>
    </div>
  ) : null);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose} role="dialog" aria-modal="true">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 p-4">
          <div className="min-w-0">
            <h2 className="break-words text-lg font-bold text-slate-900">{event.title || t('calendar.d.no_title')}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={event.status} />
              {event.status === 'PUBLISHED' && event.is_demo && (
                <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-bold text-amber-800">{t('common.demo_published')}</span>
              )}
            </div>
          </div>
          <button onClick={onClose} aria-label={t('common.close')} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"><X size={18} /></button>
        </div>
        <div className="space-y-4 p-4">
          <div className={`${isStory ? 'aspect-[9/16] max-w-[14rem]' : 'aspect-video'} mx-auto w-full overflow-hidden rounded-xl bg-slate-100`}>
            <MediaPreview
              src={event.media_url}
              mediaType={event.media_type}
              status={event.media_generation_status}
              alt={event.title || ''}
              className="h-full w-full object-cover"
            />
          </div>
          <dl className="space-y-1.5">
            {row(t('common.property'), event.property_name)}
            {row(t('common.platform'), t(`platform.${event.platform}`))}
            {row(t('calendar.d.kind'), t(`kind.${event.kind}`))}
            {row(timeLabel, fmtDateTime(event.event_at, lang))}
            {row(t('calendar.d.language'), event.language ? t(`lang.${event.language}`) : '')}
          </dl>
          {event.caption && (
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">{t('calendar.d.caption')}</p>
              <p className="mt-1 whitespace-pre-line break-words text-sm text-slate-800">{event.caption}</p>
            </div>
          )}
          {event.cta && (
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">{t('calendar.d.cta')}</p>
              <p className="mt-1 break-words text-sm font-semibold text-slate-900">{event.cta}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Calendar() {
  const { t, lang } = useLanguage();
  const now = new Date();
  const [cursor, setCursor] = useState({ y: now.getFullYear(), m: now.getMonth() });
  const [view, setView] = useState('month');
  const [platform, setPlatform] = useState('');
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [expanded, setExpanded] = useState(null);

  const todayKey = dayKeyOf(new Date().toISOString());

  // Grid always starts on Sunday and covers whole weeks.
  const grid = useMemo(() => {
    const first = utcDate(cursor.y, cursor.m, 1);
    const start = utcDate(cursor.y, cursor.m, 1 - first.getUTCDay());
    const last = utcDate(cursor.y, cursor.m + 1, 0);
    const weeks = Math.ceil((first.getUTCDay() + last.getUTCDate()) / 7);
    const days = Array.from({ length: weeks * 7 }, (_, i) => utcDate(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate() + i));
    return { days, start: ymd(days[0]), end: ymd(days[days.length - 1]) };
  }, [cursor]);

  const range = useMemo(() => {
    if (view === 'list') {
      const today = new Date();
      const from = utcDate(today.getFullYear(), today.getMonth(), today.getDate());
      const to = utcDate(today.getFullYear(), today.getMonth(), today.getDate() + 90);
      return { start: ymd(from), end: ymd(to) };
    }
    return { start: grid.start, end: grid.end };
  }, [view, grid]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { start: range.start, end: range.end };
      if (platform) params.platform = platform;
      const response = await api.get('/api/calendar', { params });
      setEvents(Array.isArray(response.data) ? response.data : []);
      setError('');
    } catch (requestError) {
      setError(errorText(requestError, t('calendar.load_failed')));
    } finally {
      setLoading(false);
    }
  }, [range, platform, t]);

  useEffect(() => { load(); }, [load]);

  const sorted = useMemo(
    () => [...events].sort((a, b) => (parseApiDate(a.event_at)?.getTime() || 0) - (parseApiDate(b.event_at)?.getTime() || 0)),
    [events],
  );

  const byDay = useMemo(() => {
    const map = {};
    sorted.forEach((event) => {
      const key = dayKeyOf(event.event_at);
      if (key) (map[key] ||= []).push(event);
    });
    return map;
  }, [sorted]);

  const listEvents = useMemo(() => {
    const nowMs = Date.now() - 3600000;
    return sorted.filter((event) => (parseApiDate(event.event_at)?.getTime() || 0) >= nowMs);
  }, [sorted]);

  const weekdays = useMemo(() => {
    const fmt = new Intl.DateTimeFormat(localeOf(lang), { weekday: 'short', timeZone: 'UTC' });
    return Array.from({ length: 7 }, (_, i) => fmt.format(utcDate(2023, 0, 1 + i))); // 2023-01-01 is a Sunday
  }, [lang]);

  const monthTitle = new Intl.DateTimeFormat(localeOf(lang), { month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(utcDate(cursor.y, cursor.m, 1));

  const shift = (delta) => {
    const d = utcDate(cursor.y, cursor.m + delta, 1);
    setCursor({ y: d.getUTCFullYear(), m: d.getUTCMonth() });
    setExpanded(null);
  };
  const goToday = () => {
    const d = new Date();
    setCursor({ y: d.getFullYear(), m: d.getMonth() });
  };

  const dayLabel = (value) => new Intl.DateTimeFormat(localeOf(lang), { weekday: 'long', day: 'numeric', month: 'long', timeZone: APP_TIMEZONE })
    .format(parseApiDate(value));

  const btn = 'inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50';
  const monthEmpty = !loading && !error && events.length === 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('calendar.title')}</h1>
          <p className="text-sm text-slate-500">{t('calendar.subtitle')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            aria-label={t('common.platform')}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
          >
            <option value="">{t('calendar.all_platforms')}</option>
            {PLATFORMS.map((p) => <option key={p} value={p}>{t(`platform.${p}`)}</option>)}
          </select>
          <div className="inline-flex overflow-hidden rounded-lg border border-slate-300 bg-white text-sm font-medium">
            {['month', 'list'].map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-3 py-2 ${view === v ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50'}`}
              >
                {t(`calendar.view_${v}`)}
              </button>
            ))}
          </div>
          <button onClick={load} className={btn} aria-label={t('common.refresh')}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {view === 'month' && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button onClick={() => shift(-1)} className={btn} aria-label={t('calendar.prev')}><ChevronLeft size={16} className="rtl:rotate-180" /></button>
            <button onClick={goToday} className={btn}>{t('calendar.today')}</button>
            <button onClick={() => shift(1)} className={btn} aria-label={t('calendar.next')}><ChevronRight size={16} className="rtl:rotate-180" /></button>
            <h2 className="ms-2 text-lg font-bold text-slate-900">{monthTitle}</h2>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-600">
            <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded bg-violet-300" />{t('calendar.legend_scheduled')}</span>
            <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded bg-emerald-300" />{t('calendar.legend_published')}</span>
          </div>
        </div>
      )}

      {error ? (
        <div className="space-y-3 rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-800">
          <p className="font-semibold">{t('calendar.load_failed')}</p>
          <p className="text-sm">{error}</p>
          <button onClick={load} className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700">
            <RotateCw size={14} />{t('common.retry')}
          </button>
        </div>
      ) : view === 'month' ? (
        <div className="space-y-3">
          {loading && <p className="flex items-center gap-2 text-sm text-slate-500"><RefreshCw size={14} className="animate-spin" />{t('common.loading')}</p>}
          {monthEmpty && <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-500">{t('calendar.empty_month')}</p>}
          <div className="overflow-x-auto">
            <div className="min-w-[44rem] overflow-hidden rounded-xl border border-slate-200 bg-white">
              <div className="grid grid-cols-7 border-b border-slate-200 bg-slate-50 text-center text-xs font-semibold text-slate-600">
                {weekdays.map((name) => <div key={name} className="py-2">{name}</div>)}
              </div>
              <div className="grid grid-cols-7">
                {grid.days.map((day) => {
                  const key = ymd(day);
                  const inMonth = day.getUTCMonth() === cursor.m;
                  const list = byDay[key] || [];
                  const open = expanded === key;
                  const shown = open ? list : list.slice(0, MAX_CHIPS);
                  return (
                    <div key={key} className={`min-h-28 space-y-1 border-b border-e border-slate-100 p-1.5 ${inMonth ? 'bg-white' : 'bg-slate-50/70'}`}>
                      <div className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${key === todayKey ? 'bg-indigo-600 text-white' : inMonth ? 'text-slate-700' : 'text-slate-400'}`}>
                        {day.getUTCDate()}
                      </div>
                      {shown.map((event) => <EventChip key={`${event.id}-${event.platform}`} event={event} lang={lang} t={t} onOpen={setSelected} />)}
                      {list.length > MAX_CHIPS && (
                        <button
                          onClick={() => setExpanded(open ? null : key)}
                          className="px-1.5 text-start text-[11px] font-semibold text-indigo-600 hover:underline"
                        >
                          {open ? t('calendar.less') : t('calendar.more', { n: list.length - MAX_CHIPS })}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-500"><RefreshCw size={18} className="animate-spin" />{t('common.loading')}</div>
      ) : listEvents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center font-semibold text-slate-600">{t('calendar.empty_list')}</div>
      ) : (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {listEvents.map((event) => (
            <li key={`${event.id}-${event.platform}`}>
              <button onClick={() => setSelected(event)} className="flex w-full flex-wrap items-center gap-3 px-4 py-3 text-start hover:bg-slate-50">
                <div className="w-44 shrink-0 text-sm">
                  <p className="font-semibold text-slate-900">{dayLabel(event.event_at)}</p>
                  <p className="text-xs text-slate-500">{timeOf(event.event_at, lang)}</p>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-900">{event.title || t('calendar.d.no_title')}</p>
                  <p className="truncate text-xs text-slate-500">{event.property_name} · {t(`platform.${event.platform}`)} · {t(`kind.${event.kind}`)}</p>
                </div>
                <StatusBadge status={event.status} />
                {event.status === 'PUBLISHED' && event.is_demo && (
                  <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-bold text-amber-800">{t('common.demo_published')}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected && <EventModal event={selected} onClose={() => setSelected(null)} t={t} lang={lang} />}
    </div>
  );
}
