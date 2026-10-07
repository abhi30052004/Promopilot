import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Save, AlertTriangle, AlertCircle, ShieldCheck, Bot, Loader2, HardDrive } from 'lucide-react';
import api from '../lib/api';
import { useLanguage } from '../lib/LanguageContext';
import { useToast } from '../lib/toast';
import { errorText, PLATFORMS, DEFAULT_PLATFORMS } from '../lib/format';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const inputCls = 'w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

function normalize(data) {
  return {
    approval_mode: data.approval_mode === 'AUTOMATION' ? 'AUTOMATION' : 'HUMAN',
    platforms_enabled: Array.isArray(data.platforms_enabled) ? [...data.platforms_enabled] : [...DEFAULT_PLATFORMS],
    default_language: data.default_language === 'he' ? 'he' : 'en',
    contact_email: data.contact_email || '',
    posts_per_day: Number.isFinite(Number(data.posts_per_day)) ? Number(data.posts_per_day) : 3,
    stories_per_day: Number.isFinite(Number(data.stories_per_day)) ? Number(data.stories_per_day) : 3,
    brand_tone: data.brand_tone || '',
  };
}

const same = (a, b) => JSON.stringify(Array.isArray(a) ? [...a].sort() : a) === JSON.stringify(Array.isArray(b) ? [...b].sort() : b);

function Section({ title, hint, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {hint && <p className="mt-0.5 text-sm text-slate-500">{hint}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function Settings() {
  const { t } = useLanguage();
  const toast = useToast();
  const [meta, setMeta] = useState({ supported_platforms: PLATFORMS, openai_configured: true, story_duration_seconds: 10 });
  const [original, setOriginal] = useState(null);
  const [form, setForm] = useState(null);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      const res = await api.get('/api/settings');
      const data = res.data || {};
      const norm = normalize(data);
      setOriginal(norm);
      setForm(norm);
      setMeta({
        supported_platforms: data.supported_platforms?.length ? data.supported_platforms : PLATFORMS,
        openai_configured: data.openai_configured !== false,
        story_duration_seconds: data.story_duration_seconds || 10,
      });
    } catch (e) {
      setLoadError(errorText(e, t('settings.load_failed')));
    } finally {
      setLoading(false);
    }
    try {
      const res = await api.get('/api/media/usage');
      setUsage(res.data);
    } catch {
      setUsage(null);
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const errors = useMemo(() => {
    if (!form) return {};
    const out = {};
    if (form.contact_email && !EMAIL_RE.test(form.contact_email.trim())) out.contact_email = t('settings.contact.invalid');
    if (!Number.isInteger(form.posts_per_day) || form.posts_per_day < 1 || form.posts_per_day > 10) out.posts_per_day = t('settings.invalid_number');
    if (!Number.isInteger(form.stories_per_day) || form.stories_per_day < 0 || form.stories_per_day > 15) out.stories_per_day = t('settings.invalid_number');
    if (form.platforms_enabled.length === 0) out.platforms_enabled = t('settings.platform_required');
    return out;
  }, [form, t]);

  const changed = useMemo(() => {
    if (!form || !original) return {};
    const diff = {};
    for (const key of Object.keys(original)) {
      const value = key === 'contact_email' || key === 'brand_tone' ? String(form[key]).trim() : form[key];
      if (!same(value, original[key])) diff[key] = value;
    }
    return diff;
  }, [form, original]);

  const dirty = Object.keys(changed).length > 0;
  const hasErrors = Object.keys(errors).length > 0;

  const save = async () => {
    if (!dirty || hasErrors) return;
    setSaving(true);
    try {
      await api.put('/api/settings', changed);
      toast.success(t('settings.saved'));
      setOriginal((o) => ({ ...o, ...changed }));
      setForm((f) => ({ ...f, ...changed }));
    } catch (e) {
      toast.error(`${t('settings.save_failed')} ${errorText(e, '')}`.trim());
    } finally {
      setSaving(false);
    }
  };

  const togglePlatform = (p) => {
    const list = form.platforms_enabled;
    set('platforms_enabled', list.includes(p) ? list.filter((x) => x !== p) : [...list, p]);
  };

  const parseNum = (v) => (v === '' ? NaN : Number(v));

  if (loading && !form) {
    return <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-500">{t('common.loading')}</div>;
  }
  if (loadError && !form) {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        <AlertCircle size={18} className="shrink-0" />
        <span className="flex-1 min-w-0 break-words">{loadError}</span>
        <button onClick={load} className="rounded-lg bg-red-600 px-3 py-1.5 text-white hover:bg-red-700">{t('common.retry')}</button>
      </div>
    );
  }
  if (!form) return null;

  const modes = [
    { id: 'HUMAN', icon: ShieldCheck },
    { id: 'AUTOMATION', icon: Bot },
  ];
  const percent = usage ? Math.min(100, Math.max(0, Number(usage.percent_used) || 0)) : 0;

  return (
    <div className="max-w-3xl space-y-6 pb-24">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{t('settings.title')}</h1>
        <p className="text-sm text-slate-500 mt-1">{t('settings.subtitle')}</p>
      </div>

      {!meta.openai_configured && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <span>{t('settings.openai_missing')}</span>
        </div>
      )}

      <Section title={t('settings.mode.title')}>
        <div role="radiogroup" className="grid gap-3 sm:grid-cols-2">
          {modes.map(({ id, icon: Icon }) => {
            const active = form.approval_mode === id;
            return (
              <label
                key={id}
                className={`flex cursor-pointer items-start gap-3 rounded-xl border-2 p-4 transition-colors ${
                  active ? 'border-indigo-600 bg-indigo-50' : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <input
                  type="radio"
                  name="approval_mode"
                  value={id}
                  checked={active}
                  onChange={() => set('approval_mode', id)}
                  className="mt-1 h-4 w-4 accent-indigo-600"
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-2 font-semibold text-slate-900">
                    <Icon size={18} className={active ? 'text-indigo-600' : 'text-slate-400'} />
                    {t(`settings.mode.${id}`)}
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{t(`settings.mode.${id}_desc`)}</p>
                </div>
              </label>
            );
          })}
        </div>

        {form.approval_mode === 'AUTOMATION' && (
          <div className="mt-4 rounded-xl border border-violet-200 bg-violet-50 p-4">
            <div className="text-sm font-semibold text-violet-900">{t('settings.mode.auto_title')}</div>
            <ol className="mt-2 list-decimal space-y-1 ps-5 text-sm text-violet-900">
              {[1, 2, 3, 4, 5, 6].map((n) => <li key={n}>{t(`settings.mode.auto_${n}`)}</li>)}
            </ol>
            <p className="mt-3 text-xs text-violet-800">{t('settings.mode.auto_note')}</p>
          </div>
        )}
      </Section>

      <Section title={t('settings.platforms.title')} hint={t('settings.platforms.hint')}>
        <div className="flex flex-wrap gap-2">
          {meta.supported_platforms.map((p) => {
            const on = form.platforms_enabled.includes(p);
            return (
              <label
                key={p}
                className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                  on ? 'border-indigo-600 bg-indigo-50 text-indigo-800' : 'border-slate-200 text-slate-700 hover:bg-slate-50'
                }`}
              >
                <input type="checkbox" checked={on} onChange={() => togglePlatform(p)} className="h-4 w-4 accent-indigo-600" />
                {t(`platform.${p}`)}
              </label>
            );
          })}
        </div>
        {errors.platforms_enabled && <p className="mt-2 text-xs text-red-600">{errors.platforms_enabled}</p>}
      </Section>

      <Section title={t('settings.language.title')}>
        <div className="inline-flex rounded-lg border border-slate-200 p-1">
          {['en', 'he'].map((code) => (
            <button
              key={code}
              type="button"
              onClick={() => set('default_language', code)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium ${
                form.default_language === code ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {t(`lang.${code}`)}
            </button>
          ))}
        </div>
      </Section>

      <Section title={t('settings.contact.title')} hint={t('settings.contact.hint')}>
        <input
          type="email"
          value={form.contact_email}
          onChange={(e) => set('contact_email', e.target.value)}
          className={inputCls}
          dir="ltr"
          aria-invalid={Boolean(errors.contact_email)}
        />
        {errors.contact_email && <p className="mt-1 text-xs text-red-600">{errors.contact_email}</p>}
      </Section>

      <Section title={t('settings.volume.title')}>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block text-sm font-medium text-slate-700">
            {t('settings.posts_per_property')}
            <input
              type="number"
              min={1}
              max={10}
              value={Number.isNaN(form.posts_per_day) ? '' : form.posts_per_day}
              onChange={(e) => set('posts_per_day', parseNum(e.target.value))}
              className={`${inputCls} mt-1`}
            />
            <span className="text-xs font-normal text-slate-400">{t('settings.posts_hint')}</span>
            {errors.posts_per_day && <span className="block text-xs font-normal text-red-600">{errors.posts_per_day}</span>}
          </label>
          <label className="block text-sm font-medium text-slate-700">
            {t('settings.stories_per_property')}
            <input
              type="number"
              min={0}
              max={15}
              value={Number.isNaN(form.stories_per_day) ? '' : form.stories_per_day}
              onChange={(e) => set('stories_per_day', parseNum(e.target.value))}
              className={`${inputCls} mt-1`}
            />
            <span className="text-xs font-normal text-slate-400">{t('settings.stories_hint')}</span>
            {errors.stories_per_day && <span className="block text-xs font-normal text-red-600">{errors.stories_per_day}</span>}
          </label>
          <label className="block text-sm font-medium text-slate-700">
            {t('settings.story_duration')}
            <input
              type="text"
              readOnly
              value={t('common.seconds', { n: meta.story_duration_seconds })}
              className={`${inputCls} mt-1 bg-slate-50 text-slate-500`}
            />
            <span className="text-xs font-normal text-slate-400">{t('settings.story_duration_hint')}</span>
          </label>
        </div>
      </Section>

      <Section title={t('settings.brand_tone')} hint={t('settings.brand_tone_hint')}>
        <input
          type="text"
          value={form.brand_tone}
          onChange={(e) => set('brand_tone', e.target.value)}
          className={inputCls}
        />
      </Section>

      {usage && (
        <Section title={t('settings.storage.title')}>
          <div className="flex items-center gap-2 text-sm text-slate-700">
            <HardDrive size={16} className="text-slate-400" />
            {t('settings.storage.usage', { used: usage.used_mb, cap: usage.cap_mb, percent: Math.round(percent) })}
            <span className="ms-auto text-xs text-slate-400">{t('settings.storage.files', { n: usage.file_count })}</span>
          </div>
          <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full ${percent >= 90 ? 'bg-red-500' : percent >= 70 ? 'bg-amber-500' : 'bg-indigo-600'}`}
              style={{ width: `${percent}%` }}
            />
          </div>
        </Section>
      )}

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
          <span className={`text-sm ${dirty ? 'text-amber-600' : 'text-slate-400'}`}>
            {dirty ? t('settings.unsaved') : t('settings.no_changes')}
          </span>
          <button
            onClick={save}
            disabled={!dirty || hasErrors || saving}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {saving ? t('settings.saving') : t('settings.save')}
          </button>
        </div>
      </div>
    </div>
  );
}
