import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CheckCircle, ExternalLink, LoaderCircle, MapPin, RefreshCw, Search, Sparkles, X, XCircle,
} from 'lucide-react';
import MediaPreview from '../components/MediaPreview';
import StatusBadge from '../components/StatusBadge';
import api from '../lib/api';
import { useLanguage } from '../lib/LanguageContext';
import { useToast } from '../lib/toast';
import { errorText, fmtDate, fmtDateTime, parseApiDate, timeAgo } from '../lib/format';

const RECENT = [['', 'content.recent.any'], ['1', 'content.recent.1m'], ['5', 'content.recent.5m'], ['60', 'content.recent.1h'], ['1440', 'content.recent.24h'], ['10080', 'content.recent.7d']];

const PAGE_SIZE = 60;
const POLL_MS = 5000;
const PRESET_ARTICLES = 'https://tzelahahar.co.il/en/articles';
const PRESET_PROPERTIES = 'https://tzelahahar.co.il/';
const GENERATING = ['PENDING', 'PROCESSING'];

const itemType = (item) => (item.type === 'article' ? 'article' : 'property');

function hostname(url) {
  if (!url) return '';
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; }
}

function Modal({ children, onClose, wide = false, busy = false }) {
  return (
    <div
      className="fixed inset-0 z-50 bg-slate-950/50 flex items-center justify-center p-4"
      onMouseDown={() => { if (!busy) onClose(); }}
    >
      <div
        className={`bg-white rounded-2xl shadow-2xl w-full ${wide ? 'max-w-4xl' : 'max-w-md'} max-h-[90vh] overflow-y-auto`}
        onMouseDown={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

function Spinner({ size = 16 }) {
  return <LoaderCircle size={size} className="animate-spin" />;
}

function ApprovalBadge({ item, t }) {
  if (item.approval_status === 'APPROVED') {
    return <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-emerald-100 text-emerald-800">{t('properties.badge.approved')}</span>;
  }
  if (item.approval_status === 'REJECTED') {
    return <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-rose-100 text-rose-800">{t('properties.badge.rejected')}</span>;
  }
  return <StatusBadge status="PENDING" />;
}

function ActionButtons({ item, onAction, onGenerate, onRetryImages, busyKey, t, compact = false }) {
  const disabled = !!busyKey;
  const size = compact ? 'py-2 text-sm' : 'py-2.5 text-sm';
  return (
    <div className="flex flex-wrap gap-2">
      {item.approval_status === 'PENDING' && (
        <>
          <button
            onClick={() => onAction('approve', item)}
            disabled={disabled}
            className={`flex-1 min-w-24 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium flex items-center justify-center gap-1.5 px-3 disabled:opacity-50 ${size}`}
          >
            <CheckCircle size={15} /> {t('common.approve')}
          </button>
          <button
            onClick={() => onAction('reject', item)}
            disabled={disabled}
            className={`flex-1 min-w-24 border border-rose-200 text-rose-700 hover:bg-rose-50 rounded-lg font-medium flex items-center justify-center gap-1.5 px-3 disabled:opacity-50 ${size}`}
          >
            <XCircle size={15} /> {t('common.reject')}
          </button>
        </>
      )}
      {item.media_status === 'FAILED' && onRetryImages && (
        <button
          onClick={() => onRetryImages(item)}
          disabled={disabled}
          className={`border border-amber-300 text-amber-800 hover:bg-amber-50 rounded-lg font-medium flex items-center justify-center gap-1.5 px-3 disabled:opacity-50 ${size}`}
        >
          {busyKey === `${item.id}:images` ? <Spinner /> : <RefreshCw size={15} />} {t('properties.retry_images')}
        </button>
      )}
    </div>
  );
}

function ItemCard({ item, onOpen, onAction, busyKey, t, lang }) {
  const type = itemType(item);
  const generating = GENERATING.includes(item.content_generation_status);
  return (
    <article className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden flex flex-col">
      <button type="button" onClick={() => onOpen(item)} className="h-48 bg-slate-100 overflow-hidden block w-full text-start">
        <MediaPreview src={item.preview_url} status={item.media_status === 'PROCESSING' || item.media_status === 'FAILED' ? item.media_status : undefined} alt={item.title || item.name || ''} />
      </button>
      <div className="p-4 flex-1 flex flex-col gap-2.5">
        <div className="flex items-start justify-between gap-3">
          <button type="button" onClick={() => onOpen(item)} className="text-start font-bold text-slate-800 hover:text-indigo-700 line-clamp-2">
            {item.title || item.name || t('properties.untitled')}
          </button>
          <div className="shrink-0"><ApprovalBadge item={item} t={t} /></div>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-600">{t(`properties.type_label.${type}`)}</span>
          {item.category && <span>{item.category}</span>}
          {item.location && <span className="inline-flex items-center gap-1"><MapPin size={12} />{item.location}</span>}
        </div>
        <p className="text-sm text-slate-600 line-clamp-3">{item.description || item.summary || t('properties.no_description')}</p>
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
          <span className="truncate">{hostname(item.source_url || item.url)}</span>
          <span title={fmtDateTime(item.scraped_at, lang)}>{fmtDate(item.scraped_at, lang)} · {timeAgo(item.scraped_at, lang)}</span>
        </div>
        {item.approval_status === 'REJECTED' && item.rejection_reason && (
          <p className="text-xs text-rose-700 bg-rose-50 rounded-lg px-3 py-2 break-words">{t('properties.rejection_reason', { reason: item.rejection_reason })}</p>
        )}
        {generating && (
          <p className="text-xs text-sky-700 flex items-center gap-1.5"><Spinner size={13} /> {t('properties.generating')}</p>
        )}
        {item.approval_status === 'APPROVED' && !generating && item.content_counts && (item.content_counts.post || item.content_counts.story) ? (
          <p className="text-xs text-slate-500">{t('properties.generated_counts', { posts: item.content_counts.post || 0, stories: item.content_counts.story || 0 })}</p>
        ) : null}
        {item.approval_status === 'PENDING' && (
          <div className="mt-auto pt-1">
            <ActionButtons item={item} onAction={onAction} busyKey={busyKey} t={t} compact />
          </div>
        )}
      </div>
    </article>
  );
}

function ConfirmModal({ action, busy, onCancel, onConfirm, t }) {
  const [reason, setReason] = useState('');
  const isReject = action.type === 'reject';
  const name = action.item.title || action.item.name || t('properties.untitled');
  return (
    <Modal onClose={onCancel} busy={busy}>
      <div className="p-6 flex flex-col gap-4">
        <h3 className="text-lg font-bold text-slate-800">{t(isReject ? 'properties.reject_title' : 'properties.approve_title')}</h3>
        <p className="text-sm text-slate-600 break-words">{t(isReject ? 'properties.reject_body' : 'properties.approve_body', { name })}</p>
        {isReject && (
          <label className="flex flex-col gap-1.5 text-sm font-medium text-slate-700">
            {t('common.reason_optional')}
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={3}
              placeholder={t('properties.reject_reason_placeholder')}
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm font-normal"
            />
          </label>
        )}
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} disabled={busy} className="px-4 py-2 rounded-lg border border-slate-200 text-sm disabled:opacity-50">{t('common.cancel')}</button>
          <button
            onClick={() => onConfirm(reason.trim())}
            disabled={busy}
            className={`px-4 py-2 rounded-lg text-white text-sm font-medium flex items-center gap-2 disabled:opacity-60 ${isReject ? 'bg-rose-600 hover:bg-rose-700' : 'bg-emerald-600 hover:bg-emerald-700'}`}
          >
            {busy && <Spinner />} {t(isReject ? 'properties.reject_confirm' : 'properties.approve_confirm')}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function SyncModal({ syncing, onClose, onStart, t }) {
  const [url, setUrl] = useState(PRESET_ARTICLES);
  const [missing, setMissing] = useState(false);
  const presetClass = (value) => `px-3 py-2 rounded-lg border text-sm text-start ${url === value ? 'border-indigo-500 bg-indigo-50 text-indigo-800' : 'border-slate-200 hover:bg-slate-50'}`;
  return (
    <Modal onClose={onClose} busy={syncing}>
      <div className="p-6 flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-lg font-bold text-slate-800">{t('properties.sync_title')}</h3>
          <button onClick={onClose} disabled={syncing} aria-label={t('common.close')}><X size={18} /></button>
        </div>
        <p className="text-sm text-slate-500">{t('properties.sync_hint')}</p>
        <div className="flex flex-col gap-2">
          <button type="button" onClick={() => setUrl(PRESET_ARTICLES)} disabled={syncing} className={presetClass(PRESET_ARTICLES)}>{t('properties.sync_preset_articles')}</button>
          <button type="button" onClick={() => setUrl(PRESET_PROPERTIES)} disabled={syncing} className={presetClass(PRESET_PROPERTIES)}>{t('properties.sync_preset_properties')}</button>
        </div>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-slate-700">
          {t('properties.sync_url')}
          <input
            dir="ltr"
            value={url}
            onChange={(event) => { setUrl(event.target.value); setMissing(false); }}
            disabled={syncing}
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm font-normal text-start"
          />
        </label>
        {missing && <p className="text-xs text-rose-600">{t('properties.sync_url_required')}</p>}
        {syncing && <p className="text-sm text-sky-700 flex items-center gap-2"><Spinner /> {t('properties.sync_running')}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 rounded-lg border border-slate-200 text-sm">{t('common.close')}</button>
          <button
            onClick={() => { if (!url.trim()) { setMissing(true); return; } onStart(url.trim()); }}
            disabled={syncing}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium flex items-center gap-2 disabled:opacity-60"
          >
            {syncing ? <Spinner /> : <RefreshCw size={15} />} {t('properties.sync_start')}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase text-slate-400 mb-0.5">{label}</div>
      <div className="text-sm text-slate-700 break-words">{children}</div>
    </div>
  );
}

function DetailModal({ state, onClose, onAction, onGenerate, onRetryImages, busyKey, t, lang }) {
  const { item, loading, error } = state;
  const notSupplied = t('common.not_supplied');
  // Only show images that are really stored; broken source URLs are never shown as tiles.
  const images = (item?.property_images || []).filter((image) => image.media_url);
  const retriedRef = useRef(null);
  useEffect(() => {
    // Nothing usable stored yet -> kick off storing / AI replacement once for this item.
    if (item?.id && !loading && images.length === 0 && item.media_status !== 'PROCESSING' && retriedRef.current !== item.id) {
      retriedRef.current = item.id;
      onRetryImages?.(item);
    }
  }, [item?.id, loading, images.length, item?.media_status]); // eslint-disable-line react-hooks/exhaustive-deps
  const amenities = Array.isArray(item?.amenities) ? item.amenities : [];
  const tags = Array.isArray(item?.tags) ? item.tags : [];
  const sourceUrl = item?.source_url || item?.url;
  const counts = item?.content_counts || {};
  const imageLabel = (image) => {
    if (image.is_ai_generated) return t('properties.detail.image_ai');
    if (image.status === 'VALID' || image.status === 'COMPLETED' || image.status === 'SUCCESS') return t('properties.detail.image_original');
    return t('properties.detail.image_unavailable');
  };

  return (
    <Modal onClose={onClose} wide>
      <div className="sticky top-0 z-10 bg-white border-b border-slate-100 p-5 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-bold text-xl text-slate-800 break-words">{item?.title || item?.name || t('properties.detail.title')}</h3>
          {item && <div className="mt-1.5"><ApprovalBadge item={item} t={t} /></div>}
        </div>
        <button onClick={onClose} aria-label={t('common.close')}><X size={20} /></button>
      </div>

      {loading && !item?.content && !item?.title ? (
        <div className="h-64 flex items-center justify-center text-indigo-600"><Spinner size={32} /></div>
      ) : (
        <div className="p-6 flex flex-col gap-6">
          {error && <p className="text-sm text-rose-700 bg-rose-50 rounded-lg px-3 py-2">{error}</p>}

          <ActionButtons item={item} onAction={onAction} onGenerate={onGenerate} onRetryImages={onRetryImages} busyKey={busyKey} t={t} />

          <section>
            <h4 className="font-semibold text-slate-800 mb-3">{t('properties.detail.images')}</h4>
            {images.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {images.map((image) => (
                  <div key={image.id} className="aspect-square rounded-lg overflow-hidden border border-slate-100 relative bg-slate-100">
                    <MediaPreview
                      src={image.media_url}
                      status={image.media_status === 'PENDING' || image.media_status === 'PROCESSING' ? image.media_status : undefined}
                      alt={item.title || item.name || ''}
                    />
                    <span className="absolute bottom-2 start-2 bg-black/70 text-white text-[10px] px-2 py-1 rounded">{imageLabel(image)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="aspect-video max-w-sm rounded-lg overflow-hidden border border-slate-100">
                <MediaPreview src={item.preview_url} status={item.media_status === 'PROCESSING' || item.media_status === 'FAILED' ? item.media_status : undefined} alt={item.title || item.name || ''} />
              </div>
            )}
            {images.length === 0 && <p className="text-xs text-slate-400 mt-2">{t('properties.detail.no_images')}</p>}
          </section>

          <section className="grid md:grid-cols-2 gap-4">
            <Field label={t('properties.detail.location')}>{item.location || notSupplied}</Field>
            <Field label={t('properties.detail.price')}>{item.price || notSupplied}</Field>
            <Field label={t('properties.category')}>{item.category || notSupplied}</Field>
            <Field label={t('properties.detail.language')}>{item.language ? (t(`lang.${item.language}`) || item.language) : notSupplied}</Field>
            <Field label={t('properties.detail.scraped_at')}>{fmtDateTime(item.scraped_at, lang)}</Field>
            {item.source_published_at && <Field label={t('properties.detail.published_at')}>{fmtDateTime(item.source_published_at, lang)}</Field>}
            <Field label={t('properties.detail.source_url')}>
              {sourceUrl ? (
                <a href={sourceUrl} target="_blank" rel="noreferrer" dir="ltr" className="text-indigo-600 hover:underline inline-flex items-center gap-1 break-all">
                  <ExternalLink size={13} className="shrink-0" /> {sourceUrl}
                </a>
              ) : notSupplied}
            </Field>
            <Field label={t('properties.detail.approval_status')}><StatusBadge status={item.approval_status || 'PENDING'} /></Field>
            <Field label={t('properties.detail.media_status')}>{item.media_status ? <StatusBadge status={item.media_status} /> : notSupplied}</Field>
            <Field label={t('properties.detail.content_status')}>
              <span className="inline-flex items-center gap-2">
                {item.content_generation_status ? <StatusBadge status={item.content_generation_status} /> : notSupplied}
                {GENERATING.includes(item.content_generation_status) && <Spinner size={14} />}
              </span>
            </Field>
            <Field label={t('properties.detail.content_counts')}>
              {t('properties.detail.content_counts_value', { posts: counts.post || 0, stories: counts.story || 0 })}
            </Field>
            {item.approved_at && <Field label={t('properties.detail.approved_at')}>{fmtDateTime(item.approved_at, lang)}</Field>}
            {item.rejected_at && <Field label={t('properties.detail.rejected_at')}>{fmtDateTime(item.rejected_at, lang)}</Field>}
            {item.rejection_reason && <Field label={t('common.reason_optional')}>{item.rejection_reason}</Field>}
          </section>

          <section className="grid md:grid-cols-2 gap-4">
            <Field label={t('properties.detail.amenities')}>
              {amenities.length ? (
                <div className="flex flex-wrap gap-1.5">{amenities.map((a) => <span key={a} className="bg-slate-100 rounded px-2 py-0.5 text-xs">{a}</span>)}</div>
              ) : notSupplied}
            </Field>
            <Field label={t('properties.detail.tags')}>
              {tags.length ? (
                <div className="flex flex-wrap gap-1.5">{tags.map((tag) => <span key={tag} className="bg-indigo-50 text-indigo-700 rounded px-2 py-0.5 text-xs">{tag}</span>)}</div>
              ) : notSupplied}
            </Field>
          </section>

          <section className="flex flex-col gap-4">
            <Field label={t('properties.detail.description')}><p className="whitespace-pre-wrap">{item.description || notSupplied}</p></Field>
            <Field label={t('properties.detail.full_text')}>
              <p className="whitespace-pre-wrap max-h-96 overflow-y-auto bg-slate-50 rounded-lg p-3 border border-slate-100">{item.content || notSupplied}</p>
            </Field>
          </section>
        </div>
      )}
    </Modal>
  );
}

export default function Properties() {
  const { t, lang } = useLanguage();
  const toast = useToast();

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [tab, setTab] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [recent, setRecent] = useState('');
  const [sort, setSort] = useState('new');
  const [tickKey, setTickKey] = useState(0);
  const [visible, setVisible] = useState(PAGE_SIZE);

  const [confirm, setConfirm] = useState(null); // {type, item}
  const [busyKey, setBusyKey] = useState('');
  const [detail, setDetail] = useState(null); // {id, item, loading, error}
  const [syncOpen, setSyncOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const detailIdRef = useRef(null);

  const loadList = useCallback(async (silent = false) => {
    if (!silent) { setLoading(true); setLoadError(''); }
    try {
      const response = await api.get('/api/properties');
      setItems(Array.isArray(response.data) ? response.data : []);
      setLoadError('');
    } catch (error) {
      if (!silent) setLoadError(errorText(error, t('properties.load_failed')));
    } finally {
      if (!silent) setLoading(false);
    }
  }, [t]);

  const loadDetail = useCallback(async (id, silent = false) => {
    try {
      const response = await api.get(`/api/properties/${id}`);
      if (detailIdRef.current !== id) return;
      setDetail({ id, item: response.data, loading: false, error: '' });
    } catch (error) {
      if (detailIdRef.current !== id || silent) return;
      setDetail((current) => (current ? { ...current, loading: false, error: errorText(error, t('properties.detail.load_failed')) } : current));
    }
  }, [t]);

  useEffect(() => { loadList(); }, [loadList]);

  // Poll while any item is generating content (list and open detail).
  const anyGenerating = items.some((item) => GENERATING.includes(item.content_generation_status));
  const detailGenerating = detail?.item && GENERATING.includes(detail.item.content_generation_status);
  useEffect(() => {
    if (!anyGenerating && !detailGenerating) return undefined;
    const timer = setInterval(() => {
      loadList(true);
      if (detailIdRef.current) loadDetail(detailIdRef.current, true);
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [anyGenerating, detailGenerating, loadList, loadDetail]);

  useEffect(() => { setVisible(PAGE_SIZE); }, [tab, typeFilter, search, recent, sort]);
  // refresh the relative times / recency filter every 30s
  useEffect(() => {
    const id = setInterval(() => setTickKey((n) => n + 1), 30000);
    return () => clearInterval(id);
  }, []);

  function openDetail(item) {
    detailIdRef.current = item.id;
    setDetail({ id: item.id, item, loading: true, error: '' });
    loadDetail(item.id);
  }

  function closeDetail() {
    detailIdRef.current = null;
    setDetail(null);
  }

  function mergeItem(updated) {
    if (!updated || updated.id == null) return;
    setItems((list) => list.map((entry) => (entry.id === updated.id ? { ...entry, ...updated } : entry)));
    setDetail((current) => (current && current.id === updated.id ? { ...current, item: { ...current.item, ...updated } } : current));
  }

  async function confirmAction(reason) {
    const { type, item } = confirm;
    setBusyKey(`${item.id}:${type}`);
    try {
      const body = type === 'approve' ? { language: lang } : { reason };
      const response = await api.post(`/api/properties/${item.id}/${type}`, body);
      mergeItem(response.data);
      toast.success(t(type === 'approve' ? 'properties.approve_ok' : 'properties.reject_ok'));
      setConfirm(null);
      loadList(true);
      if (detailIdRef.current === item.id) loadDetail(item.id, true);
    } catch (error) {
      toast.error(errorText(error, t('properties.action_failed')));
      setConfirm(null);
      loadList(true);
    } finally {
      setBusyKey('');
    }
  }

  async function generateContent(item) {
    setBusyKey(`${item.id}:generate`);
    try {
      await api.post(`/api/properties/${item.id}/generate-content`, { language: lang });
      toast.success(t('properties.generate_ok'));
      loadList(true);
      if (detailIdRef.current === item.id) loadDetail(item.id, true);
    } catch (error) {
      toast.error(errorText(error, t('properties.generate_failed')));
    } finally {
      setBusyKey('');
    }
  }

  async function retryImages(item) {
    setBusyKey(`${item.id}:images`);
    try {
      await api.post(`/api/properties/${item.id}/validate-images`);
      toast.success(t('properties.retry_images_ok'));
      loadList(true);
      if (detailIdRef.current === item.id) loadDetail(item.id, true);
    } catch (error) {
      toast.error(errorText(error, t('properties.retry_images_failed')));
    } finally {
      setBusyKey('');
    }
  }

  async function startSync(url) {
    setSyncing(true);
    try {
      const response = await api.post('/api/properties/sync', { url }, { timeout: 600000 });
      const results = response.data?.results || {};
      toast.success(t('properties.sync_done', {
        created: results.created || 0,
        updated: results.updated || 0,
        failed: results.failed || 0,
      }));
      setSyncOpen(false);
      loadList(true);
    } catch (error) {
      toast.error(errorText(error, t('properties.sync_failed')));
    } finally {
      setSyncing(false);
    }
  }

  const baseFiltered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    const cutoff = recent ? Date.now() - Number(recent) * 60000 : null;
    const time = (item) => parseApiDate(item.scraped_at || item.created_at)?.getTime() || 0;
    return items
      .filter((item) => {
        if (typeFilter !== 'all' && itemType(item) !== typeFilter) return false;
        if (cutoff !== null && time(item) < cutoff) return false;
        if (!term) return true;
        const haystack = `${item.title || ''} ${item.name || ''} ${item.location || ''} ${item.description || ''} ${item.category || ''}`.toLocaleLowerCase();
        return haystack.includes(term);
      })
      .sort((a, b) => (sort === 'new' ? time(b) - time(a) || b.id - a.id : time(a) - time(b) || a.id - b.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, search, typeFilter, recent, sort, tickKey]);

  const counts = useMemo(() => {
    const result = { ALL: baseFiltered.length, PENDING: 0, APPROVED: 0, REJECTED: 0 };
    baseFiltered.forEach((item) => { if (result[item.approval_status] !== undefined) result[item.approval_status] += 1; });
    return result;
  }, [baseFiltered]);

  const filtered = useMemo(
    () => (tab === 'ALL' ? baseFiltered : baseFiltered.filter((item) => item.approval_status === tab)),
    [baseFiltered, tab],
  );

  const tabs = [
    ['ALL', 'properties.tab.all'],
    ['PENDING', 'properties.tab.pending'],
    ['APPROVED', 'properties.tab.approved'],
    ['REJECTED', 'properties.tab.rejected'],
  ];

  return (
    <div className="flex flex-col gap-5 max-w-7xl mx-auto pb-10">
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-6 rounded-xl shadow-sm border border-slate-100">
        <div>
          <h2 className="text-xl font-bold text-slate-800">{t('properties.title')}</h2>
          <p className="text-sm text-slate-500">{t('properties.subtitle')}</p>
        </div>
        <button
          onClick={() => setSyncOpen(true)}
          className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium flex items-center gap-2"
        >
          {syncing ? <Spinner /> : <RefreshCw size={16} />} {syncing ? t('properties.sync_running_short') : t('properties.sync')}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1.5">
          {tabs.map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-3.5 py-1.5 rounded-full text-sm font-medium border ${tab === key ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'}`}
            >
              {t(label)} <span className={tab === key ? 'text-indigo-100' : 'text-slate-400'}>({counts[key]})</span>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3 ms-auto">
          <select
            value={recent}
            onChange={(event) => setRecent(event.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
            aria-label={t('content.recent.label')}
          >
            {RECENT.map(([value, key]) => <option key={value} value={value}>{t(key)}</option>)}
          </select>
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
            aria-label={t('content.sort.label')}
          >
            <option value="new">{t('content.sort.new')}</option>
            <option value="old">{t('content.sort.old')}</option>
          </select>
          <select
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="all">{t('properties.type.all')}</option>
            <option value="article">{t('properties.type.article')}</option>
            <option value="property">{t('properties.type.property')}</option>
          </select>
          <div className="relative">
            <Search size={16} className="absolute start-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('properties.search')}
              className="ps-9 pe-3 py-2 border border-slate-200 rounded-lg text-sm w-72 max-w-full bg-white"
            />
          </div>
        </div>
      </div>

      {syncing && !syncOpen && (
        <div className="text-sm text-sky-700 bg-sky-50 border border-sky-100 rounded-lg px-4 py-2.5 flex items-center gap-2">
          <Spinner /> {t('properties.sync_running')}
        </div>
      )}

      {loading ? (
        <div className="h-64 flex items-center justify-center text-indigo-600"><Spinner size={32} /></div>
      ) : loadError ? (
        <div className="bg-white rounded-xl border border-rose-100 p-10 text-center flex flex-col items-center gap-3">
          <p className="text-rose-700 text-sm">{loadError}</p>
          <button onClick={() => loadList()} className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium flex items-center gap-2">
            <RefreshCw size={15} /> {t('common.retry')}
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-100 p-12 text-center text-slate-500 text-sm">
          {items.length === 0 ? t('properties.empty_none') : t('properties.empty')}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.slice(0, visible).map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                onOpen={openDetail}
                onAction={(type, target) => setConfirm({ type, item: target })}
                busyKey={busyKey}
                t={t}
                lang={lang}
              />
            ))}
          </div>
          {filtered.length > visible && (
            <div className="flex justify-center">
              <button
                onClick={() => setVisible((value) => value + PAGE_SIZE)}
                className="px-5 py-2 rounded-lg border border-slate-200 bg-white text-sm font-medium hover:bg-slate-50"
              >
                {t('properties.show_more', { n: filtered.length - visible })}
              </button>
            </div>
          )}
        </>
      )}

      {detail && (
        <DetailModal
          state={detail}
          onClose={closeDetail}
          onAction={(type, target) => setConfirm({ type, item: target })}
          onGenerate={generateContent}
          onRetryImages={retryImages}
          busyKey={busyKey}
          t={t}
          lang={lang}
        />
      )}

      {confirm && (
        <ConfirmModal
          action={confirm}
          busy={busyKey === `${confirm.item.id}:${confirm.type}`}
          onCancel={() => setConfirm(null)}
          onConfirm={confirmAction}
          t={t}
        />
      )}

      {syncOpen && (
        <SyncModal syncing={syncing} onClose={() => setSyncOpen(false)} onStart={startSync} t={t} />
      )}
    </div>
  );
}
