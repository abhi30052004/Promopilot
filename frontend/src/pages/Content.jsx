import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Film, LoaderCircle, RefreshCw, Sparkles } from 'lucide-react';
import ContentCard from '../components/ContentCard';
import api from '../lib/api';
import { useLanguage } from '../lib/LanguageContext';
import { useToast } from '../lib/toast';
import { DEFAULT_PLATFORMS, PLATFORMS, errorText } from '../lib/format';

const FILTERS = ['ALL', 'PENDING', 'APPROVED', 'SCHEDULED', 'PUBLISHED', 'REJECTED'];
const POST_TYPES = [['1', 'PROPERTY_HIGHLIGHT'], ['2', 'DESTINATION'], ['3', 'EMOTIONAL']];
const STORY_TYPES = [['1', 'HOOK'], ['2', 'MESSAGE'], ['3', 'CTA']];

function matches(item, filter) {
  switch (filter) {
    case 'PENDING': return item.approval_status === 'PENDING';
    case 'APPROVED': return item.approval_status === 'APPROVED';
    case 'SCHEDULED': return item.publish_status === 'SCHEDULED';
    case 'PUBLISHED': return item.publish_status === 'PUBLISHED';
    case 'REJECTED': return item.approval_status === 'REJECTED';
    default: return true;
  }
}

function GeneratePanel({ kind, properties, onDone }) {
  const { t, lang } = useLanguage();
  const toast = useToast();
  const isStory = kind === 'story';
  const [propertyId, setPropertyId] = useState('');
  const [variant, setVariant] = useState('1');
  const [language, setLanguage] = useState(lang);
  const [platforms, setPlatforms] = useState(DEFAULT_PLATFORMS);
  const [busy, setBusy] = useState(false);
  const types = isStory ? STORY_TYPES : POST_TYPES;

  useEffect(() => setLanguage(lang), [lang]);

  const toggle = (p) => setPlatforms((l) => (l.includes(p) ? l.filter((x) => x !== p) : [...l, p]));

  async function generate() {
    if (!propertyId) return toast.error(t('content.select_property'));
    if (!platforms.length) return toast.error(t('dialog.select_platform'));
    setBusy(true);
    try {
      const { data } = await api.post(`/api/properties/${propertyId}/generate-content`, {
        kinds: [kind], variants: [Number(variant)], language, platform_targets: platforms,
      });
      const failed = (data.errors || []).length && !(data.posts.length || data.stories.length);
      if (failed) toast.error(data.errors.join('; '));
      else toast.success(t(isStory ? 'content.story_created' : 'content.post_created'));
      onDone();
    } catch (error) {
      toast.error(errorText(error, t('common.error')));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 flex items-center gap-2 font-bold text-slate-800">
        {isStory ? <Film size={18} /> : <Sparkles size={18} />}
        {t(isStory ? 'content.manual_story' : 'content.manual_post')}
      </h3>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
          {t('common.property')}
          <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2">
            <option value="">{t('content.select_property')}</option>
            {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
          {t('common.language')}
          <select value={language} onChange={(e) => setLanguage(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2">
            <option value="en">{t('lang.en')}</option>
            <option value="he">{t('lang.he')}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
          {t(isStory ? 'content.story_variant' : 'content.post_type')}
          <select value={variant} onChange={(e) => setVariant(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2">
            {types.map(([value, angle]) => <option key={value} value={value}>{value}. {t(`card.angle.${angle}`)}</option>)}
          </select>
        </label>
        <div className="flex flex-col gap-1 text-sm font-medium text-slate-700">
          {t('common.platforms')}
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {PLATFORMS.slice(0, 3).map((p) => (
              <label key={p} className="flex items-center gap-1.5 font-normal">
                <input type="checkbox" checked={platforms.includes(p)} onChange={() => toggle(p)} className="accent-indigo-600" />
                {t(`platform.${p}`)}
              </label>
            ))}
          </div>
        </div>
      </div>
      <button onClick={generate} disabled={busy} className="mt-4 flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
        {busy ? <LoaderCircle size={16} className="animate-spin" /> : isStory ? <Film size={16} /> : <Sparkles size={16} />}
        {busy ? t('content.generating') : t(isStory ? 'content.generate_story' : 'content.generate_post')}
      </button>
    </section>
  );
}

export default function Content() {
  const { t } = useLanguage();
  const [items, setItems] = useState([]);
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('post');
  const [filter, setFilter] = useState('ALL');
  const [langFilter, setLangFilter] = useState('');

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [content, props] = await Promise.all([
        api.get('/api/content'),
        api.get('/api/properties', { params: { approval_status: 'APPROVED' } }),
      ]);
      setItems(content.data);
      // only approved items can generate content (also guards against an older API ignoring the filter)
      setProperties(props.data.filter((p) => p.approval_status === 'APPROVED'));
      setError('');
    } catch (e) {
      setError(errorText(e, t('common.load_failed')));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  // keep polling while a story video is still rendering
  const rendering = items.some((i) => ['PENDING', 'GENERATING'].includes(i.media_generation_status));
  useEffect(() => {
    if (!rendering) return undefined;
    const id = setInterval(() => load(true), 6000);
    return () => clearInterval(id);
  }, [rendering, load]);

  const ofKind = useMemo(() => items.filter((i) => i.kind === tab && (!langFilter || i.language === langFilter)), [items, tab, langFilter]);
  const visible = useMemo(() => ofKind.filter((i) => matches(i, filter)), [ofKind, filter]);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 pb-10">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-100 bg-white p-6 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-slate-800">{t('nav.content')}</h2>
          <p className="text-sm text-slate-500">{t('content.subtitle')}</p>
        </div>
        <button onClick={() => load()} className="flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> {t('common.refresh')}
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <GeneratePanel kind="post" properties={properties} onDone={() => load(true)} />
        <GeneratePanel kind="story" properties={properties} onDone={() => load(true)} />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-lg bg-slate-100 p-1">
          {['post', 'story'].map((k) => (
            <button key={k} onClick={() => setTab(k)} className={`rounded-md px-4 py-1.5 text-sm font-semibold ${tab === k ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600'}`}>
              {t(k === 'post' ? 'kind.posts' : 'kind.stories')} ({items.filter((i) => i.kind === k).length})
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => setFilter(f)} className={`rounded-full border px-3 py-1 text-xs font-semibold ${filter === f ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-200 bg-white text-slate-600'}`}>
              {f === 'ALL' ? t('common.all') : t(`status.${f}`)} ({ofKind.filter((i) => matches(i, f)).length})
            </button>
          ))}
        </div>
        <select value={langFilter} onChange={(e) => setLangFilter(e.target.value)} className="ms-auto rounded-lg border border-slate-300 px-3 py-1.5 text-sm">
          <option value="">{t('common.all')} — {t('common.language')}</option>
          <option value="en">{t('lang.en')}</option>
          <option value="he">{t('lang.he')}</option>
        </select>
      </div>

      {loading ? (
        <div className="flex h-48 items-center justify-center"><RefreshCw className="animate-spin text-indigo-600" size={28} /></div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center text-rose-700">
          <p>{error}</p>
          <button onClick={() => load()} className="mt-3 rounded-lg bg-rose-600 px-4 py-2 text-sm text-white">{t('common.retry')}</button>
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center text-slate-500">{t('content.empty')}</div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((item) => <ContentCard key={item.id} item={item} onChanged={() => load(true)} />)}
        </div>
      )}
    </div>
  );
}
