import React, { useCallback, useEffect, useRef, useState } from 'react';
import { RefreshCw, AlertCircle } from 'lucide-react';
import api from '../lib/api';
import { useLanguage } from '../lib/LanguageContext';
import { fmtDateTime, errorText, PLATFORMS } from '../lib/format';
import { LOG_ACTIONS } from '../lib/i18n/logs';
import StatusBadge from '../components/StatusBadge';

const selectCls = 'rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500';

export default function Logs() {
  const { t, lang } = useLanguage();
  const [events, setEvents] = useState([]);
  const [action, setAction] = useState('');
  const [platform, setPlatform] = useState('');
  const [auto, setAuto] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(true);

  const load = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true);
    try {
      const res = await api.get('/api/logs', { params: { type: 'automation', limit: 200, action, platform } });
      if (!mounted.current) return;
      const rows = Array.isArray(res.data) ? res.data : [];
      // tolerate both the new event shape and the older log shape
      setEvents(rows
        .map((e) => ({
          ...e,
          timestamp: e.timestamp || e.created_at,
          action: e.action || e.agent,
          entity: e.entity || e.entity_type,
          entityId: e.entityId ?? e.entity_id ?? e.content_item_id,
        }))
        .filter((e) => e.action));
      setError('');
    } catch (e) {
      if (!mounted.current) return;
      setError(errorText(e, t('logs.load_failed')));
    } finally {
      if (mounted.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [action, platform, t]);

  useEffect(() => {
    mounted.current = true;
    load();
    return () => { mounted.current = false; };
  }, [load]);

  useEffect(() => {
    if (!auto) return undefined;
    const timer = setInterval(() => load(true), 10000);
    return () => clearInterval(timer);
  }, [auto, load]);

  const actionLabel = (code) => {
    const key = `logs.action.${code}`;
    const text = t(key);
    return text === key ? String(code || '').replace(/_/g, ' ').toLowerCase() : text;
  };
  const platformLabel = (p) => (p ? t(`platform.${p}`) : '—');
  const langLabel = (l) => (l ? t(`lang.${l}`) : '—');
  const modeLabel = (m) => (m ? t(`mode.${m}`) : '—');
  const entityText = (e) => [e.entity, e.entityId != null && e.entityId !== '' ? `#${e.entityId}` : ''].filter(Boolean).join(' ') || '—';

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('logs.title')}</h1>
          <p className="text-sm text-slate-500 mt-1">{t('logs.subtitle')}</p>
        </div>
        <button
          onClick={() => load(true)}
          disabled={refreshing}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          {t('common.refresh')}
        </button>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
          {t('logs.filter.action')}
          <select value={action} onChange={(e) => setAction(e.target.value)} className={selectCls}>
            <option value="">{t('logs.filter.all_actions')}</option>
            {LOG_ACTIONS.map((code) => (
              <option key={code} value={code}>{actionLabel(code)}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
          {t('logs.filter.platform')}
          <select value={platform} onChange={(e) => setPlatform(e.target.value)} className={selectCls}>
            <option value="">{t('logs.filter.all_platforms')}</option>
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>{t(`platform.${p}`)}</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 pb-2 text-sm text-slate-700">
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} className="h-4 w-4 accent-indigo-600" />
          {t('logs.auto_refresh')}
        </label>
        <span className="ms-auto pb-2 text-xs text-slate-400">{t('logs.count', { n: events.length })}</span>
      </div>

      {error && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertCircle size={18} className="shrink-0" />
          <span className="flex-1 min-w-0 break-words">{error}</span>
          <button onClick={() => load(true)} className="rounded-lg bg-red-600 px-3 py-1.5 text-white hover:bg-red-700">
            {t('common.retry')}
          </button>
        </div>
      )}

      {loading && events.length === 0 && !error && (
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-500">{t('common.loading')}</div>
      )}

      {!loading && !error && events.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-500">{t('logs.empty')}</div>
      )}

      {events.length > 0 && (
        <>
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  {['time', 'action', 'entity', 'status', 'mode', 'language', 'platform', 'error'].map((col) => (
                    <th key={col} className="px-4 py-3 text-start font-semibold whitespace-nowrap">{t(`logs.col.${col}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {events.map((e) => (
                  <tr key={e.id} className="align-top hover:bg-slate-50">
                    <td className="px-4 py-3 whitespace-nowrap text-slate-600">{fmtDateTime(e.timestamp, lang)}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">{actionLabel(e.action)}</div>
                      <div className="font-mono text-[11px] text-slate-400" dir="ltr">{e.action}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-700 whitespace-nowrap">{entityText(e)}</td>
                    <td className="px-4 py-3">{e.status ? <StatusBadge status={e.status} /> : '—'}</td>
                    <td className="px-4 py-3 text-slate-700 whitespace-nowrap">{modeLabel(e.mode)}</td>
                    <td className="px-4 py-3 text-slate-700 whitespace-nowrap">{langLabel(e.language)}</td>
                    <td className="px-4 py-3 text-slate-700 whitespace-nowrap">{platformLabel(e.platform)}</td>
                    <td className="px-4 py-3 max-w-xs break-words text-red-600">{e.error || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="space-y-3 md:hidden">
            {events.map((e) => (
              <div key={e.id} className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-900">{actionLabel(e.action)}</div>
                    <div className="font-mono text-[11px] text-slate-400" dir="ltr">{e.action}</div>
                  </div>
                  {e.status && <StatusBadge status={e.status} />}
                </div>
                <div className="mt-2 text-xs text-slate-500">{fmtDateTime(e.timestamp, lang)}</div>
                <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                  <div><dt className="text-slate-400">{t('logs.col.entity')}</dt><dd className="text-slate-700 break-words">{entityText(e)}</dd></div>
                  <div><dt className="text-slate-400">{t('logs.col.mode')}</dt><dd className="text-slate-700">{modeLabel(e.mode)}</dd></div>
                  <div><dt className="text-slate-400">{t('logs.col.language')}</dt><dd className="text-slate-700">{langLabel(e.language)}</dd></div>
                  <div><dt className="text-slate-400">{t('logs.col.platform')}</dt><dd className="text-slate-700">{platformLabel(e.platform)}</dd></div>
                </dl>
                {e.error && <div className="mt-3 break-words rounded-lg bg-red-50 p-2 text-xs text-red-600">{e.error}</div>}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
