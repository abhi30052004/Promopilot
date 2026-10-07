import React, { useState, useEffect } from 'react';
import { Save, Settings2, Globe, Clock, AlertCircle, RefreshCw } from 'lucide-react';
import api from '../lib/api';

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [original, setOriginal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const res = await api.get('/api/settings');
      const parsed = {
        posts_per_day: parseInt(res.data.posts_per_day) || 3,
        stories_per_day: parseInt(res.data.stories_per_day) || 3,
        story_duration_seconds: parseInt(res.data.story_duration_seconds) || 10,
        max_ai_images_per_property: parseInt(res.data.max_ai_images_per_property) || 3,
        approval_mode: res.data.approval_mode || 'HUMAN',
        brand_tone: res.data.brand_tone || 'relaxing',
        languages: res.data.languages || ['he'],
        platforms_enabled: res.data.platforms_enabled || [],
        post_slots: res.data.post_slots || [],
        story_slots: res.data.story_slots || [],
      };
      setSettings(parsed);
      setOriginal(JSON.stringify(parsed));
    } catch {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/api/settings', settings);
      setOriginal(JSON.stringify(settings));
      showToast('ההגדרות נשמרו בהצלחה!');
    } catch (e) {
      showToast('שגיאה בשמירת הגדרות', 'error');
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = settings && original !== JSON.stringify(settings);

  const toggleArray = (field, value) => {
    setSettings(prev => {
      const arr = prev[field] || [];
      if (arr.includes(value)) {
        return { ...prev, [field]: arr.filter(x => x !== value) };
      }
      return { ...prev, [field]: [...arr, value] };
    });
  };

  const handleSlots = (field, valStr) => {
    const slots = valStr.split(',').map(s => s.trim()).filter(s => s.match(/^([01]\d|2[0-3]):([0-5]\d)$/));
    setSettings(prev => ({ ...prev, [field]: slots }));
  };

  if (loading || !settings) {
    return <div className="flex justify-center items-center h-64"><RefreshCw className="animate-spin text-slate-400" /></div>;
  }

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6 pb-20 relative">
      {toast && (
        <div className={`fixed bottom-4 end-4 px-6 py-3 rounded-lg shadow-lg text-white ${toast.type === 'error' ? 'bg-red-500' : 'bg-emerald-500'} z-50 transition-all`}>
          {toast.msg}
        </div>
      )}

      <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 flex justify-between items-center sticky top-16 z-20">
        <div>
          <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
            <Settings2 size={24} className="text-indigo-600" />
            הגדרות סוכן ופרסום
          </h2>
          <p className="text-sm text-slate-500 mt-1">קבע את חוקי הפעולה לאוטומציה של יצירת התוכן</p>
        </div>
        <button 
          onClick={handleSave}
          disabled={!hasChanges || saving}
          className={`flex items-center gap-2 px-6 py-2.5 rounded-lg font-medium transition-all shadow-sm ${hasChanges && !saving ? 'bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer' : 'bg-slate-100 text-slate-400 cursor-not-allowed'}`}
        >
          {saving ? <RefreshCw size={18} className="animate-spin" /> : <Save size={18} />}
          שמור שינויים
        </button>
      </div>

      {hasChanges && (
        <div className="bg-amber-50 border border-amber-200 text-amber-700 px-4 py-3 rounded-lg flex items-center gap-2 text-sm font-medium animate-in fade-in slide-in-from-top-4">
          <AlertCircle size={16} /> יש לך שינויים שלא נשמרו!
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Core Strategy */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
          <div className="bg-slate-50 border-b border-slate-100 px-5 py-3 font-semibold text-slate-700">
            תפוקה ואסטרטגיה
          </div>
          <div className="p-5 flex flex-col gap-5">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">פוסטים ביום</label>
                <input 
                  type="number" min="1" max="10"
                  value={settings.posts_per_day}
                  onChange={e => setSettings({...settings, posts_per_day: parseInt(e.target.value) || 1})}
                  className="w-full border border-slate-200 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none bg-slate-50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">סטוריז ביום</label>
                <input 
                  type="number" min="0" max="15"
                  value={settings.stories_per_day}
                  onChange={e => setSettings({...settings, stories_per_day: parseInt(e.target.value) || 0})}
                  className="w-full border border-slate-200 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none bg-slate-50"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">תמונות AI לכל נכס</label>
                <input 
                  type="number" min="0" max="10"
                  value={settings.max_ai_images_per_property}
                  onChange={e => setSettings({...settings, max_ai_images_per_property: parseInt(e.target.value) || 3})}
                  className="w-full border border-slate-200 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none bg-slate-50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">אורך סטורי (שניות)</label>
                <input 
                  type="number" min="5" max="30"
                  value={settings.story_duration_seconds}
                  onChange={e => setSettings({...settings, story_duration_seconds: parseInt(e.target.value) || 10})}
                  className="w-full border border-slate-200 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none bg-slate-50"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">מצב אישור ברירת מחדל</label>
              <div className="flex gap-4 bg-slate-50 p-1 rounded-lg border border-slate-200">
                <label className={`flex-1 flex justify-center items-center py-2 rounded-md cursor-pointer transition-colors text-sm font-medium ${settings.approval_mode === 'HUMAN' ? 'bg-white shadow-sm text-indigo-700' : 'text-slate-600 hover:bg-slate-100'}`}>
                  <input type="radio" name="mode" className="sr-only" checked={settings.approval_mode === 'HUMAN'} onChange={() => setSettings({...settings, approval_mode: 'HUMAN'})} />
                  ידני (דורש אישור אנושי)
                </label>
                <label className={`flex-1 flex justify-center items-center py-2 rounded-md cursor-pointer transition-colors text-sm font-medium ${settings.approval_mode === 'AUTOMATION' ? 'bg-white shadow-sm text-indigo-700' : 'text-slate-600 hover:bg-slate-100'}`}>
                  <input type="radio" name="mode" className="sr-only" checked={settings.approval_mode === 'AUTOMATION'} onChange={() => setSettings({...settings, approval_mode: 'AUTOMATION'})} />
                  אוטומציה (אישור אוטומטי)
                </label>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">טון שיווקי (Brand Tone)</label>
              <select 
                value={settings.brand_tone}
                onChange={e => setSettings({...settings, brand_tone: e.target.value})}
                className="w-full border border-slate-200 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none bg-slate-50"
              >
                <option value="relaxing">מרגיע ויוקרתי (Relaxing)</option>
                <option value="energetic">אנרגטי וצעיר (Energetic)</option>
                <option value="romantic">רומנטי וזוגי (Romantic)</option>
                <option value="family">משפחתי ומזמין (Family-oriented)</option>
                <option value="professional">רשמי ומקצועי (Professional)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Channels & Language */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
          <div className="bg-slate-50 border-b border-slate-100 px-5 py-3 font-semibold text-slate-700 flex items-center gap-2">
            <Globe size={18} /> שפות ופלטפורמות
          </div>
          <div className="p-5 flex flex-col gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">שפות נתמכות (Agents)</label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={settings.languages.includes('he')} onChange={() => toggleArray('languages', 'he')} className="rounded text-indigo-600 w-4 h-4" />
                  <span className="text-sm">עברית (he)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={settings.languages.includes('en')} onChange={() => toggleArray('languages', 'en')} className="rounded text-indigo-600 w-4 h-4" />
                  <span className="text-sm">אנגלית (en)</span>
                </label>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">פלטפורמות יעד להפצה</label>
              <div className="grid grid-cols-2 gap-3">
                {['facebook', 'instagram', 'tiktok', 'x', 'telegram'].map(p => (
                  <label key={p} className="flex items-center gap-2 cursor-pointer bg-slate-50 p-2 rounded-lg border border-slate-100 hover:border-slate-300 transition-colors">
                    <input type="checkbox" checked={settings.platforms_enabled.includes(p)} onChange={() => toggleArray('platforms_enabled', p)} className="rounded text-indigo-600 w-4 h-4" />
                    <span className="text-sm capitalize">{p}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Scheduling Times */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden md:col-span-2">
          <div className="bg-slate-50 border-b border-slate-100 px-5 py-3 font-semibold text-slate-700 flex items-center gap-2">
            <Clock size={18} /> תזמון חלונות פרסום (Slots)
          </div>
          <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">חלונות תזמון לפוסטים (HH:MM)</label>
              <p className="text-xs text-slate-500 mb-2">הזן מופרד בפסיקים. סוכן התכנון ישתמש בחלונות אלו.</p>
              <input 
                type="text" dir="ltr"
                defaultValue={settings.post_slots?.join(', ')}
                onBlur={e => handleSlots('post_slots', e.target.value)}
                className="w-full border border-slate-200 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none font-mono"
                placeholder="09:00, 15:00, 19:00"
              />
              <div className="flex flex-wrap gap-2 mt-3">
                {settings.post_slots?.map(s => <span key={s} className="bg-indigo-50 text-indigo-700 px-2 py-1 rounded text-xs font-mono">{s}</span>)}
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">חלונות תזמון לסטוריז (HH:MM)</label>
              <p className="text-xs text-slate-500 mb-2">הזן מופרד בפסיקים. סוכן התכנון ישתמש בחלונות אלו.</p>
              <input 
                type="text" dir="ltr"
                defaultValue={settings.story_slots?.join(', ')}
                onBlur={e => handleSlots('story_slots', e.target.value)}
                className="w-full border border-slate-200 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none font-mono"
                placeholder="11:00, 17:00, 20:00"
              />
              <div className="flex flex-wrap gap-2 mt-3">
                {settings.story_slots?.map(s => <span key={s} className="bg-emerald-50 text-emerald-700 px-2 py-1 rounded text-xs font-mono">{s}</span>)}
              </div>
            </div>
          </div>
          <div className="bg-slate-50 p-4 border-t border-slate-100 flex items-center justify-between">
            <span className="text-sm text-slate-600">אזור זמן של המערכת (קריאה בלבד)</span>
            <span className="px-3 py-1 bg-slate-200 text-slate-700 rounded-full text-xs font-mono tracking-wide">Asia/Jerusalem</span>
          </div>
        </div>

      </div>
    </div>
  );
}
