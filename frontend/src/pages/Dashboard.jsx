import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw, ShieldCheck, Bot, AlertCircle, Settings as SettingsIcon } from 'lucide-react';
import api from '../lib/api';
import { useLanguage } from '../lib/LanguageContext';
import { errorText } from '../lib/format';

const GROUPS = [
  {
    id: 'properties',
    stats: [
      ['total_scraped', 'text-slate-900'],
      ['pending_properties', 'text-amber-600'],
      ['approved_properties', 'text-emerald-600'],
      ['rejected_properties', 'text-rose-600'],
    ],
  },
  {
    id: 'content',
    stats: [
      ['posts_generated', 'text-indigo-600'],
      ['stories_generated', 'text-indigo-600'],
      ['pending_content', 'text-amber-600'],
      ['scheduled', 'text-violet-600'],
      ['published', 'text-emerald-600'],
      ['rejected_content', 'text-rose-600'],
    ],
  },
  {
    id: 'media',
    stats: [
      ['images_generated', 'text-sky-600'],
      ['videos_generated', 'text-sky-600'],
      ['failed_generations', 'text-red-600'],
    ],
  },
];

export default function Dashboard() {
  const { t, lang } = useLanguage();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [updatedAt, setUpdatedAt] = useState(null);
  const mounted = useRef(true);

  const load = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true);
    try {
      const res = await api.get('/api/dashboard/stats');
      if (!mounted.current) return;
      setStats(res.data);
      setError('');
      setUpdatedAt(new Date());
    } catch (e) {
      if (!mounted.current) return;
      setError(errorText(e, t('dashboard.load_failed')));
    } finally {
      if (mounted.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [t]);

  useEffect(() => {
    mounted.current = true;
    load();
    const timer = setInterval(() => load(true), 15000);
    return () => {
      mounted.current = false;
      clearInterval(timer);
    };
  }, [load]);

  const mode = stats?.current_mode === 'AUTOMATION' ? 'AUTOMATION' : 'HUMAN';
  const ModeIcon = mode === 'AUTOMATION' ? Bot : ShieldCheck;
  const time = updatedAt
    ? new Intl.DateTimeFormat(lang === 'he' ? 'he-IL' : 'en-GB', { timeStyle: 'medium' }).format(updatedAt)
    : '';

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('dashboard.title')}</h1>
          <p className="text-sm text-slate-500 mt-1">{t('dashboard.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400 hidden sm:inline">
            {updatedAt ? t('dashboard.updated', { time }) : ''} · {t('dashboard.auto_refresh')}
          </span>
          <button
            onClick={() => load(true)}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
            {t('common.refresh')}
          </button>
        </div>
      </div>

      {loading && !stats && (
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-500">{t('common.loading')}</div>
      )}

      {error && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertCircle size={18} className="shrink-0" />
          <span className="flex-1 min-w-0 break-words">{error}</span>
          <button onClick={() => load(true)} className="rounded-lg bg-red-600 px-3 py-1.5 text-white hover:bg-red-700">
            {t('common.retry')}
          </button>
        </div>
      )}

      {stats && (
        <>
          <Link
            to="/settings"
            className={`flex flex-wrap items-center gap-4 rounded-2xl border p-5 shadow-sm transition-shadow hover:shadow-md ${
              mode === 'AUTOMATION' ? 'border-violet-200 bg-violet-50' : 'border-indigo-200 bg-indigo-50'
            }`}
          >
            <div className={`rounded-xl p-3 ${mode === 'AUTOMATION' ? 'bg-violet-600' : 'bg-indigo-600'} text-white`}>
              <ModeIcon size={28} />
            </div>
            <div className="flex-1 min-w-[12rem]">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t('dashboard.mode.label')}</div>
              <div className="text-xl font-bold text-slate-900">{t(`dashboard.mode.${mode}`)}</div>
              <div className="text-sm text-slate-600 mt-0.5">{t(`dashboard.mode.${mode}_desc`)}</div>
            </div>
            <span className="inline-flex items-center gap-2 text-sm font-medium text-indigo-700">
              <SettingsIcon size={16} />
              {t('dashboard.mode.change')}
            </span>
          </Link>

          {GROUPS.map((group) => (
            <section key={group.id}>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
                {t(`dashboard.group.${group.id}`)}
              </h2>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
                {group.stats.map(([key, color]) => (
                  <div key={key} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                    <div className={`text-3xl font-bold ${color}`}>{stats[key] ?? 0}</div>
                    <div className="mt-1 text-sm text-slate-500">{t(`dashboard.stat.${key}`)}</div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </>
      )}
    </div>
  );
}
