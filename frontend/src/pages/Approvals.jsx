import { useCallback, useEffect, useState } from 'react';
import { CheckCircle, ExternalLink, LoaderCircle, RefreshCw, XCircle } from 'lucide-react';
import ContentCard from '../components/ContentCard';
import MediaPreview from '../components/MediaPreview';
import api from '../lib/api';
import { useLanguage } from '../lib/LanguageContext';
import { useToast } from '../lib/toast';
import { errorText, fmtDate } from '../lib/format';

function hostOf(url) {
  try { return new URL(url).hostname; } catch { return url || '—'; }
}

function PendingProperty({ property, onChanged }) {
  const { t, lang } = useLanguage();
  const toast = useToast();
  const [busy, setBusy] = useState(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');

  async function approve() {
    setBusy('approve');
    try {
      await api.post(`/api/properties/${property.id}/approve`, { language: lang });
      toast.success(t('approvals.approved_ok'));
      onChanged();
    } catch (error) {
      toast.error(errorText(error, t('common.error')));
    } finally {
      setBusy(null);
    }
  }

  async function reject() {
    setBusy('reject');
    try {
      await api.post(`/api/properties/${property.id}/reject`, { reason: reason || null });
      toast.success(t('approvals.rejected_ok'));
      setRejecting(false);
      setReason('');
      onChanged();
    } catch (error) {
      toast.error(errorText(error, t('common.error')));
    } finally {
      setBusy(null);
    }
  }

  return (
    <article className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm sm:flex-row">
      <div className="h-48 shrink-0 bg-slate-100 sm:h-auto sm:w-56">
        <MediaPreview src={property.preview_url} status={property.media_status} alt={property.name} />
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="text-lg font-bold text-slate-900">{property.name}</h3>
        <p className="line-clamp-4 text-sm text-slate-600">{property.description || property.content || t('common.not_supplied')}</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          {property.location && <span>{property.location}</span>}
          {property.category && <span>{property.category}</span>}
          <span>{t('common.source')}: {hostOf(property.source_url || property.url)}</span>
          <span>{t('common.scraped_at')}: {fmtDate(property.scraped_at, lang)}</span>
        </div>
        {(property.source_url || property.url) && (
          <a href={property.source_url || property.url} target="_blank" rel="noreferrer" className="flex w-fit items-center gap-1 text-xs text-indigo-600">
            <ExternalLink size={12} /> {t('common.open_source')}
          </a>
        )}
        <div className="mt-auto flex gap-2 pt-2">
          <button onClick={approve} disabled={!!busy} className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            {busy === 'approve' ? <LoaderCircle size={15} className="animate-spin" /> : <CheckCircle size={15} />} {t('common.approve')}
          </button>
          <button onClick={() => setRejecting(true)} disabled={!!busy} className="flex items-center gap-1.5 rounded-lg border border-rose-200 px-4 py-2 text-sm font-semibold text-rose-700 disabled:opacity-50">
            <XCircle size={15} /> {t('common.reject')}
          </button>
        </div>
      </div>

      {rejecting && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/50 p-4" onMouseDown={() => setRejecting(false)}>
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
            <h3 className="mb-2 text-lg font-bold">{t('approvals.reject_title', { name: property.name })}</h3>
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t('common.reason_optional')} rows={3} className="w-full rounded-lg border border-slate-300 p-3 text-sm" />
            <div className="mt-4 flex justify-end gap-3">
              <button onClick={() => setRejecting(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">{t('common.cancel')}</button>
              <button onClick={reject} disabled={busy === 'reject'} className="flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
                {busy === 'reject' && <LoaderCircle size={16} className="animate-spin" />} {t('common.reject')}
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

export default function Approvals() {
  const { t } = useLanguage();
  const [tab, setTab] = useState('properties');
  const [properties, setProperties] = useState([]);
  const [content, setContent] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [props, items] = await Promise.all([
        api.get('/api/properties', { params: { approval_status: 'PENDING' } }),
        api.get('/api/content', { params: { approval_status: 'PENDING' } }),
      ]);
      setProperties(props.data);
      setContent(items.data);
      setError('');
    } catch (e) {
      setError(errorText(e, t('common.load_failed')));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const posts = content.filter((i) => i.kind === 'post');
  const stories = content.filter((i) => i.kind === 'story');

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 pb-10">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-100 bg-white p-6 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-slate-800">{t('nav.approvals')}</h2>
          <p className="text-sm text-slate-500">{t('approvals.subtitle')}</p>
        </div>
        <button onClick={() => load()} className="flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> {t('common.refresh')}
        </button>
      </div>

      <div className="flex w-fit rounded-lg bg-slate-100 p-1">
        <button onClick={() => setTab('properties')} className={`rounded-md px-4 py-1.5 text-sm font-semibold ${tab === 'properties' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600'}`}>
          {t('approvals.pending_properties')} ({properties.length})
        </button>
        <button onClick={() => setTab('content')} className={`rounded-md px-4 py-1.5 text-sm font-semibold ${tab === 'content' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600'}`}>
          {t('approvals.pending_content')} ({content.length})
        </button>
      </div>

      {loading ? (
        <div className="flex h-48 items-center justify-center"><RefreshCw className="animate-spin text-indigo-600" size={28} /></div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center text-rose-700">
          <p>{error}</p>
          <button onClick={() => load()} className="mt-3 rounded-lg bg-rose-600 px-4 py-2 text-sm text-white">{t('common.retry')}</button>
        </div>
      ) : tab === 'properties' ? (
        properties.length === 0 ? (
          <div className="rounded-xl border bg-white p-12 text-center text-slate-500">{t('approvals.no_properties')}</div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {properties.map((p) => <PendingProperty key={p.id} property={p} onChanged={() => load(true)} />)}
          </div>
        )
      ) : content.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center text-slate-500">{t('approvals.no_content')}</div>
      ) : (
        <div className="flex flex-col gap-8">
          {[['kind.posts', posts], ['kind.stories', stories]].map(([label, list]) => list.length > 0 && (
            <section key={label}>
              <h3 className="mb-3 text-lg font-bold text-slate-800">{t(label)} ({list.length})</h3>
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
                {list.map((item) => <ContentCard key={item.id} item={item} onChanged={() => load(true)} />)}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
