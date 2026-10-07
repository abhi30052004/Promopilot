import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Clock, Mail, MessageCircle, RefreshCw, RotateCw, Send, Share2, ThumbsUp, Heart, Repeat2 } from 'lucide-react';
import MediaPreview from '../components/MediaPreview';
import StatusBadge from '../components/StatusBadge';
import api from '../lib/api';
import { useLanguage } from '../lib/LanguageContext';
import { useToast } from '../lib/toast';
import { PLATFORMS, errorText, fmtDateTime } from '../lib/format';

const SUBS = ['PUBLISHED', 'SCHEDULED', 'FAILED'];
const PLATFORM_TONE = {
  instagram: 'bg-pink-100 text-pink-800',
  facebook: 'bg-blue-100 text-blue-800',
  linkedin: 'bg-sky-100 text-sky-800',
  tiktok: 'bg-slate-900 text-white',
  x: 'bg-slate-800 text-white',
  telegram: 'bg-cyan-100 text-cyan-800',
};

function hashtagText(value) {
  if (!value) return '';
  const list = Array.isArray(value) ? value : String(value).split(/[\s,]+/);
  return list.filter(Boolean).map((tag) => (String(tag).startsWith('#') ? tag : `#${tag}`)).join(' ');
}

function PlatformBadge({ platform }) {
  const { t } = useLanguage();
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${PLATFORM_TONE[platform] || 'bg-slate-100 text-slate-700'}`}>
      {t(`platform.${platform}`)}
    </span>
  );
}

function Avatar({ name, className = '' }) {
  const initial = (name || '?').trim().charAt(0).toUpperCase();
  return (
    <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-pink-500 text-sm font-bold text-white ${className}`}>
      {initial}
    </div>
  );
}

function Media({ item, ratio }) {
  const isStory = item.kind === 'story';
  const box = isStory ? 'aspect-[9/16] max-w-xs mx-auto w-full' : `${ratio} w-full`;
  return (
    <div className={`${box} overflow-hidden bg-slate-100`}>
      <MediaPreview
        src={item.media_url}
        mediaType={item.media_type}
        status={item.media_generation_status}
        alt={item.title || item.property_name || ''}
        className="h-full w-full object-cover"
      />
    </div>
  );
}

function CaptionBlock({ item, showLink }) {
  const { t } = useLanguage();
  const tags = hashtagText(item.hashtags);
  const text = item.kind === 'story' ? [item.story_hook, item.story_message].filter(Boolean).join(' — ') || item.caption : item.caption;
  return (
    <div className="space-y-1 text-sm text-slate-800">
      {text ? <p className="whitespace-pre-line break-words">{text}</p> : <p className="text-slate-400">{t('feeds.no_caption')}</p>}
      {item.cta && <p className="font-semibold text-slate-900">{item.cta}</p>}
      {tags && <p className="break-words text-blue-600">{tags}</p>}
      {showLink && item.link && <p className="break-all text-xs text-blue-600">{item.link}</p>}
    </div>
  );
}

function CardMeta({ item, onRetry, retrying }) {
  const { t, lang } = useLanguage();
  const when = item.status === 'PUBLISHED'
    ? t('feeds.published_at', { when: fmtDateTime(item.published_at, lang) })
    : item.status === 'SCHEDULED'
      ? t('feeds.scheduled_for', { when: fmtDateTime(item.scheduled_at, lang) })
      : null;
  return (
    <div className="space-y-2 border-t border-slate-100 bg-slate-50 px-4 py-3 text-xs text-slate-600">
      <div className="flex flex-wrap items-center gap-2">
        <PlatformBadge platform={item.platform} />
        <StatusBadge status={item.status} />
        {item.status === 'PUBLISHED' && item.is_demo && (
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-bold text-amber-800">{t('common.demo_published')}</span>
        )}
        {item.kind === 'story' && (
          <span className="rounded-full bg-fuchsia-100 px-2.5 py-0.5 text-xs font-semibold text-fuchsia-800">{t('feeds.story_badge')}</span>
        )}
      </div>
      <p className="font-medium text-slate-800">{item.property_name}</p>
      {when && (
        <p className="flex items-center gap-1.5"><Clock size={13} className="shrink-0" />{when}</p>
      )}
      {item.contact_email && (
        <p className="flex items-center gap-1.5 break-all"><Mail size={13} className="shrink-0" />{t('feeds.contact', { email: item.contact_email })}</p>
      )}
      {item.status === 'FAILED' && (
        <div className="space-y-2 rounded-lg border border-red-200 bg-red-50 p-3 text-red-800">
          <p className="flex items-start gap-1.5 font-semibold"><AlertCircle size={14} className="mt-0.5 shrink-0" />{t('feeds.failed_error')}</p>
          {item.error && <p className="break-words">{item.error}</p>}
          {item.attempt ? <p className="text-red-600">{t('feeds.attempt', { n: item.attempt })}</p> : null}
          <button
            onClick={() => onRetry(item)}
            disabled={retrying}
            className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-60"
          >
            <RotateCw size={13} className={retrying ? 'animate-spin' : ''} />
            {retrying ? t('feeds.retrying') : t('feeds.retry')}
          </button>
        </div>
      )}
    </div>
  );
}

function InstagramCard({ item, ...meta }) {
  const { t } = useLanguage();
  return (
    <article className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center gap-3 px-4 py-3">
        <Avatar name={item.property_name} />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{item.property_name}</p>
          <p className="text-xs text-slate-500">{t('feeds.just_now')}</p>
        </div>
      </header>
      <Media item={item} ratio="aspect-square" />
      <div className="flex items-center gap-4 px-4 pt-3 text-slate-700">
        <Heart size={20} /><MessageCircle size={20} /><Send size={20} />
      </div>
      <div className="px-4 py-3"><CaptionBlock item={item} /></div>
      <CardMeta item={item} {...meta} />
    </article>
  );
}

function FacebookCard({ item, ...meta }) {
  const { t } = useLanguage();
  return (
    <article className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center gap-3 px-4 py-3">
        <Avatar name={item.property_name} className="!bg-blue-600 !bg-none" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{item.property_name}</p>
          <p className="text-xs text-slate-500">{t('feeds.just_now')}</p>
        </div>
      </header>
      <div className="px-4 pb-3"><CaptionBlock item={item} showLink /></div>
      <Media item={item} ratio="aspect-video" />
      <div className="flex items-center justify-around border-t border-slate-100 py-2 text-xs font-medium text-slate-600">
        <span className="flex items-center gap-1.5"><ThumbsUp size={15} />{t('feeds.like')}</span>
        <span className="flex items-center gap-1.5"><MessageCircle size={15} />{t('feeds.comment')}</span>
        <span className="flex items-center gap-1.5"><Share2 size={15} />{t('feeds.share')}</span>
      </div>
      <CardMeta item={item} {...meta} />
    </article>
  );
}

function LinkedInCard({ item, ...meta }) {
  const { t } = useLanguage();
  return (
    <article className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center gap-3 px-4 py-3">
        <Avatar name={item.property_name} className="!rounded-md !bg-sky-700 !bg-none" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{item.property_name}</p>
          <p className="text-xs text-slate-500">{t('feeds.sponsored')} · {t('feeds.just_now')}</p>
        </div>
      </header>
      <div className="px-4 pb-3"><CaptionBlock item={item} showLink /></div>
      <Media item={item} ratio="aspect-video" />
      <div className="flex items-center justify-around border-t border-slate-100 py-2 text-xs font-medium text-slate-600">
        <span className="flex items-center gap-1.5"><ThumbsUp size={15} />{t('feeds.like')}</span>
        <span className="flex items-center gap-1.5"><MessageCircle size={15} />{t('feeds.comment')}</span>
        <span className="flex items-center gap-1.5"><Repeat2 size={15} />{t('feeds.repost')}</span>
        <span className="flex items-center gap-1.5"><Send size={15} />{t('feeds.send')}</span>
      </div>
      <CardMeta item={item} {...meta} />
    </article>
  );
}

function GenericCard({ item, ...meta }) {
  return (
    <article className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <Media item={item} ratio="aspect-video" />
      <div className="space-y-2 px-4 py-3">
        {item.title && <h3 className="text-sm font-semibold text-slate-900">{item.title}</h3>}
        <div className="line-clamp-4"><CaptionBlock item={item} /></div>
      </div>
      <CardMeta item={item} {...meta} />
    </article>
  );
}

function FeedCard({ item, tab, onRetry, retrying }) {
  const props = { item, onRetry, retrying };
  if (tab === 'instagram') return <InstagramCard {...props} />;
  if (tab === 'facebook') return <FacebookCard {...props} />;
  if (tab === 'linkedin') return <LinkedInCard {...props} />;
  return <GenericCard {...props} />;
}

export default function Feeds() {
  const { t } = useLanguage();
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [tab, setTab] = useState('all');
  const [sub, setSub] = useState('PUBLISHED');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [retrying, setRetrying] = useState(null);
  const mounted = useRef(true);

  const load = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      const response = await api.get('/api/feeds');
      if (!mounted.current) return;
      setItems(Array.isArray(response.data) ? response.data : []);
      setError('');
    } catch (requestError) {
      if (mounted.current) setError(errorText(requestError, t('feeds.load_failed')));
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
    const timer = setInterval(() => load(), 20000);
    return () => {
      mounted.current = false;
      clearInterval(timer);
    };
  }, [load]);

  const tabItems = useMemo(
    () => (tab === 'all' ? items : items.filter((item) => item.platform === tab)),
    [items, tab],
  );
  const visible = useMemo(() => tabItems.filter((item) => item.status === sub), [tabItems, sub]);
  const tabCount = (key) => (key === 'all' ? items.length : items.filter((item) => item.platform === key).length);
  const subCount = (key) => tabItems.filter((item) => item.status === key).length;

  async function retry(item) {
    setRetrying(item.id);
    try {
      await api.post(`/api/content/${item.content_id}/retry`, { platform: item.platform });
      toast.success(t('feeds.retry_ok', { platform: t(`platform.${item.platform}`) }));
      await load();
    } catch (requestError) {
      toast.error(`${t('feeds.retry_failed')}: ${errorText(requestError, t('common.error'))}`);
    } finally {
      setRetrying(null);
    }
  }

  const tabs = ['all', ...PLATFORMS];
  const gridCols = tab === 'all' || !['instagram', 'facebook', 'linkedin'].includes(tab)
    ? 'sm:grid-cols-2 xl:grid-cols-3'
    : 'sm:grid-cols-2';

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('feeds.title')}</h1>
          <p className="text-sm text-slate-500">{t('feeds.subtitle')}</p>
          <p className="mt-1 text-xs text-slate-400">{t('feeds.auto_refresh')}</p>
        </div>
        <button
          onClick={() => load(true)}
          disabled={refreshing}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          {t('common.refresh')}
        </button>
      </div>

      <div className="flex flex-wrap gap-2" role="tablist">
        {tabs.map((key) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${tab === key ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50'}`}
          >
            {key === 'all' ? t('feeds.tab_all') : t(`platform.${key}`)}
            <span className={`ms-2 text-xs ${tab === key ? 'text-slate-300' : 'text-slate-400'}`}>{tabCount(key)}</span>
          </button>
        ))}
      </div>

      <div className="flex gap-1 border-b border-slate-200" role="tablist">
        {SUBS.map((key) => (
          <button
            key={key}
            role="tab"
            aria-selected={sub === key}
            onClick={() => setSub(key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold ${sub === key ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}
          >
            {t(`feeds.sub.${key}`)}
            <span className="ms-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{subCount(key)}</span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-500">
          <RefreshCw size={18} className="animate-spin" />{t('common.loading')}
        </div>
      ) : error && items.length === 0 ? (
        <div className="space-y-3 rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-800">
          <p className="font-semibold">{t('feeds.load_failed')}</p>
          <p className="text-sm">{error}</p>
          <button onClick={() => load(true)} className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700">
            <RotateCw size={14} />{t('common.retry')}
          </button>
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <p className="font-semibold text-slate-700">{t('feeds.empty')}</p>
          <p className="mt-1 text-sm text-slate-500">{t('feeds.empty_hint')}</p>
        </div>
      ) : (
        <>
          {error && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">{error}</p>
          )}
          <div className={`grid grid-cols-1 items-start gap-5 ${gridCols}`}>
            {visible.map((item) => (
              <FeedCard
                key={`${item.id}-${item.platform}`}
                item={item}
                tab={tab}
                onRetry={retry}
                retrying={retrying === item.id}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
