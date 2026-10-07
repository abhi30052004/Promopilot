import React, { useState } from 'react';
import { CalendarClock, LoaderCircle, RefreshCw, Send, XCircle } from 'lucide-react';
import api from '../lib/api';
import { useLanguage } from '../lib/LanguageContext';
import { useToast } from '../lib/toast';
import { errorText, fmtDateTime } from '../lib/format';
import MediaPreview from './MediaPreview';
import PlatformDialog from './PlatformDialog';
import StatusBadge from './StatusBadge';

// One generated post or story with the real Approve & Post / Approve & Schedule / Reject actions.
export default function ContentCard({ item, onChanged }) {
  const { t, lang } = useLanguage();
  const toast = useToast();
  const [dialog, setDialog] = useState(null); // 'publish' | 'schedule' | 'reject' | null
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState('');

  const isStory = item.kind === 'story';
  const pending = item.approval_status === 'PENDING';
  const rejected = item.approval_status === 'REJECTED';
  const videoRendering = isStory && ['PENDING', 'GENERATING'].includes(item.media_generation_status);
  const platformName = (p) => t(`platform.${p}`);
  const logs = item.publish_logs || [];
  const failedLogs = logs.filter((l) => l.status === 'FAILED');

  async function run(request, onOk) {
    setBusy(true);
    try {
      const response = await request();
      onOk?.(response.data);
      setDialog(null);
      onChanged?.();
    } catch (error) {
      toast.error(`${t('card.action_failed')}: ${errorText(error, t('common.error'))}`);
    } finally {
      setBusy(false);
    }
  }

  const publish = ({ platforms }) =>
    run(() => api.post(`/api/content/${item.id}/publish`, { platforms }), (data) => {
      const names = platforms.map(platformName).join(', ');
      toast.success(t(data.demo ? 'card.published_demo' : 'card.published_ok', { platforms: names }));
    });

  const schedule = ({ platforms, scheduledAt }) =>
    run(() => api.post(`/api/content/${item.id}/schedule`, { platforms, scheduled_at: scheduledAt }), () =>
      toast.success(t('card.scheduled_ok', { when: `${scheduledAt.replace('T', ' ')}` })));

  const reject = () =>
    run(() => api.post(`/api/content/${item.id}/reject`, { reason: reason || null }), () => {
      setReason('');
      toast.success(t('card.rejected_ok'));
    });

  const retry = (platform) =>
    run(() => api.post(`/api/content/${item.id}/retry`, { platform }), () => toast.success(t('status.PUBLISHED')));

  const regenerate = () =>
    run(() => api.post(`/api/content/${item.id}/generate`), () => toast.success(t('common.regenerate')));

  return (
    <article className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className={`relative bg-slate-100 ${isStory ? 'mx-auto aspect-[9/16] w-full max-w-[260px]' : 'aspect-[4/3] w-full'}`}>
        <MediaPreview
          src={item.media_url}
          mediaType={item.media_type}
          status={item.media_generation_status}
          alt={item.title || ''}
        />
        <span className="absolute start-2 top-2 rounded-full bg-black/70 px-2.5 py-0.5 text-xs font-bold uppercase text-white">
          {t(`kind.${item.kind}`)}
        </span>
        {item.is_ai_generated && !isStory && (
          <span className="absolute end-2 top-2 rounded bg-indigo-600/90 px-2 py-0.5 text-[10px] font-semibold text-white">{t('common.ai_generated')}</span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={item.approval_status} />
          {item.publish_status && item.publish_status !== 'DRAFT' && <StatusBadge status={item.publish_status} />}
          <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">{item.language?.toUpperCase()}</span>
          {item.angle && <span className="text-xs text-slate-500">{t(`card.angle.${item.angle}`)}</span>}
        </div>

        <div>
          <h3 className="font-bold text-slate-900">{item.title || item.property_name}</h3>
          <p className="text-xs text-slate-500">{t('common.property')}: {item.property_name}</p>
        </div>

        {isStory ? (
          <div className="space-y-1 text-sm text-slate-700">
            <p className="font-semibold">{t('card.story_text')}</p>
            {item.story_hook && <p><span className="text-slate-500">{t('card.hook')}: </span>{item.story_hook}</p>}
            {item.story_message && <p><span className="text-slate-500">{t('card.message')}: </span>{item.story_message}</p>}
            <p className="text-xs text-slate-500">{t('common.duration')}: {t('common.seconds', { n: item.duration_seconds || 10 })}</p>
            {videoRendering && <p className="flex items-center gap-1 text-xs text-sky-700"><LoaderCircle size={12} className="animate-spin" />{t('card.video_rendering')}</p>}
          </div>
        ) : (
          <div className="space-y-1 text-sm text-slate-700">
            <p className="whitespace-pre-wrap">{item.caption}</p>
            {item.hashtags && <p className="text-xs text-indigo-700 break-words">{Array.isArray(item.hashtags) ? item.hashtags.join(' ') : item.hashtags}</p>}
          </div>
        )}

        {item.cta && <p className="text-sm"><span className="font-semibold">{t('card.cta')}: </span>{item.cta}</p>}
        {item.contact_email && <p className="text-xs text-slate-600">{t('common.contact')}: <span dir="ltr" className="font-mono">{item.contact_email}</span></p>}

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-semibold text-slate-500">{t('common.platforms')}:</span>
          {(item.platform_targets || []).map((p) => (
            <span key={p} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{platformName(p)}</span>
          ))}
        </div>

        {logs.length > 0 && (
          <ul className="space-y-1 rounded-lg bg-slate-50 p-2 text-xs">
            {logs.map((log) => (
              <li key={log.id} className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{platformName(log.platform)}</span>
                <span className="flex items-center gap-2">
                  {log.status === 'PUBLISHED' && log.is_demo && <span className="font-bold text-amber-700">{t('common.demo_published')}</span>}
                  <StatusBadge status={log.status} />
                  <span className="text-slate-500">{fmtDateTime(log.status === 'SCHEDULED' ? log.scheduled_at : log.published_at, lang)}</span>
                </span>
                {log.error && <span className="w-full text-rose-600">{log.error}</span>}
              </li>
            ))}
          </ul>
        )}

        {rejected && item.rejection_reason && <p className="text-xs text-rose-600">{item.rejection_reason}</p>}

        <div className="mt-auto flex flex-wrap gap-2 pt-1">
          {pending && (
            <>
              <button onClick={() => setDialog('publish')} disabled={busy || videoRendering} className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">
                <Send size={15} /> {t('card.approve_post')}
              </button>
              <button onClick={() => setDialog('schedule')} disabled={busy} className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">
                <CalendarClock size={15} /> {t('card.approve_schedule')}
              </button>
              <button onClick={() => setDialog('reject')} disabled={busy} className="flex items-center justify-center gap-1.5 rounded-lg border border-rose-200 px-3 py-2 text-sm font-semibold text-rose-700 disabled:opacity-50">
                <XCircle size={15} /> {t('common.reject')}
              </button>
            </>
          )}
          {failedLogs.map((log) => (
            <button key={log.id} onClick={() => retry(log.platform)} disabled={busy} className="flex items-center gap-1.5 rounded-lg border border-amber-300 px-3 py-2 text-sm font-semibold text-amber-800 disabled:opacity-50">
              <RefreshCw size={14} /> {t('common.retry')} · {platformName(log.platform)}
            </button>
          ))}
          {item.publish_status !== 'PUBLISHED' && (
            <button onClick={regenerate} disabled={busy} className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 disabled:opacity-50" title={t('common.regenerate')}>
              <RefreshCw size={14} className={busy ? 'animate-spin' : ''} /> {t('common.regenerate')}
            </button>
          )}
        </div>
      </div>

      <PlatformDialog
        open={dialog === 'publish' || dialog === 'schedule'}
        mode={dialog === 'schedule' ? 'schedule' : 'publish'}
        initialPlatforms={item.platform_targets}
        busy={busy}
        onClose={() => setDialog(null)}
        onConfirm={dialog === 'schedule' ? schedule : publish}
      />

      {dialog === 'reject' && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/50 p-4" onMouseDown={busy ? undefined : () => setDialog(null)}>
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <h3 className="mb-2 text-lg font-bold">{t('card.reject_reason')}</h3>
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t('common.reason_optional')} rows={3} className="w-full rounded-lg border border-slate-300 p-3 text-sm" />
            <div className="mt-4 flex justify-end gap-3">
              <button onClick={() => setDialog(null)} disabled={busy} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">{t('common.cancel')}</button>
              <button onClick={reject} disabled={busy} className="flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
                {busy && <LoaderCircle size={16} className="animate-spin" />} {t('common.reject')}
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
