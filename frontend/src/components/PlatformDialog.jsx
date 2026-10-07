import React, { useEffect, useState } from 'react';
import { LoaderCircle, X } from 'lucide-react';
import { useLanguage } from '../lib/LanguageContext';
import { DEFAULT_PLATFORMS, PLATFORMS, dateInputValue } from '../lib/format';

// mode='publish'  -> platform checkboxes, [Cancel] [Confirm publish]
// mode='schedule' -> platform checkboxes + date + time, [Cancel] [Schedule]
export default function PlatformDialog({ open, mode = 'publish', initialPlatforms, busy, onClose, onConfirm }) {
  const { t } = useLanguage();
  const [selected, setSelected] = useState(DEFAULT_PLATFORMS);
  const [date, setDate] = useState(dateInputValue(1));
  const [time, setTime] = useState('19:30');
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      const initial = (initialPlatforms || []).filter((p) => PLATFORMS.includes(p));
      setSelected(initial.length ? initial : DEFAULT_PLATFORMS);
      setDate(dateInputValue(1));
      setTime('19:30');
      setError('');
    }
  }, [open, initialPlatforms]);

  if (!open) return null;

  const toggle = (platform) =>
    setSelected((list) => (list.includes(platform) ? list.filter((p) => p !== platform) : [...list, platform]));

  function submit() {
    if (!selected.length) {
      setError(t('dialog.select_platform'));
      return;
    }
    if (mode === 'schedule') {
      if (!date || !time || new Date(`${date}T${time}`) <= new Date()) {
        setError(t('dialog.select_datetime'));
        return;
      }
      onConfirm({ platforms: selected, scheduledAt: `${date}T${time}` });
    } else {
      onConfirm({ platforms: selected });
    }
  }

  const title = mode === 'schedule' ? t('dialog.schedule.title') : t('dialog.publish.title');
  const hint = mode === 'schedule' ? t('dialog.schedule.hint') : t('dialog.publish.hint');

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/50 p-4" onMouseDown={busy ? undefined : onClose}>
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <div className="mb-1 flex items-start justify-between gap-4">
          <h3 className="text-lg font-bold text-slate-900">{title}</h3>
          <button onClick={onClose} disabled={busy} aria-label={t('common.close')}><X size={20} /></button>
        </div>
        <p className="mb-4 text-sm text-slate-500">{hint}</p>

        <div className="flex flex-col gap-2">
          {PLATFORMS.map((platform) => (
            <label key={platform} className={`flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-2.5 ${selected.includes(platform) ? 'border-indigo-400 bg-indigo-50' : 'border-slate-200'}`}>
              <input type="checkbox" checked={selected.includes(platform)} onChange={() => toggle(platform)} className="size-4 accent-indigo-600" />
              <span className="font-medium text-slate-800">{t(`platform.${platform}`)}</span>
            </label>
          ))}
        </div>

        {mode === 'schedule' && (
          <div className="mt-4 grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
              {t('dialog.schedule.date')}
              <input type="date" value={date} min={dateInputValue(0)} onChange={(e) => setDate(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2" />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
              {t('dialog.schedule.time')}
              <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2" />
            </label>
          </div>
        )}

        {error && <p className="mt-3 text-sm font-medium text-rose-600">{error}</p>}

        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} disabled={busy} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50">
            {t('common.cancel')}
          </button>
          <button onClick={submit} disabled={busy} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {busy && <LoaderCircle size={16} className="animate-spin" />}
            {mode === 'schedule' ? t('dialog.schedule.confirm') : t('dialog.publish.confirm')}
          </button>
        </div>
      </div>
    </div>
  );
}
