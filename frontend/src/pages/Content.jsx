import React, { useEffect, useMemo, useState } from 'react';
import { CalendarClock, FileText, RefreshCw, UploadCloud, X, Zap } from 'lucide-react';
import ContentDrawer from '../components/ContentDrawer';
import MediaPreview from '../components/MediaPreview';
import api from '../lib/api';

const badge = {
  draft: 'bg-slate-100 text-slate-700',
  pending_approval: 'bg-amber-100 text-amber-700',
  approved: 'bg-blue-100 text-blue-700',
  scheduled: 'bg-purple-100 text-purple-700',
  published: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
  rejected: 'bg-rose-100 text-rose-700',
};

function localDate(value = new Date()) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export default function Content() {
  const [items, setItems] = useState([]);
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [selected, setSelected] = useState(null);
  const [kind, setKind] = useState('');
  const [status, setStatus] = useState('');
  const [generateOpen, setGenerateOpen] = useState(false);
  const [generateForm, setGenerateForm] = useState({ property_id: '', date: localDate() });
  const [scheduleItem, setScheduleItem] = useState(null);
  const [scheduleForm, setScheduleForm] = useState({ scheduled_at: '', platform: 'instagram' });
  const [message, setMessage] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const [contentResponse, propertyResponse] = await Promise.all([
        api.get('/api/content'),
        api.get('/api/properties'),
      ]);
      setItems(contentResponse.data);
      setProperties(propertyResponse.data);
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Could not load content.' });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const propertyNames = useMemo(
    () => Object.fromEntries(properties.map((property) => [property.id, property.name])),
    [properties],
  );
  const visible = items.filter((item) => (!kind || item.kind === kind) && (!status || item.status === status));
  const today = localDate();
  const now = new Date();
  const sections = [
    ['Today', visible.filter((item) => (item.generation_date || item.created_at?.slice(0, 10)) === today)],
    ['Upcoming', visible.filter((item) => (item.generation_date || item.created_at?.slice(0, 10)) !== today && item.scheduled_at && new Date(item.scheduled_at) > now)],
    ['Previous', visible.filter((item) => (item.generation_date || item.created_at?.slice(0, 10)) !== today && (!item.scheduled_at || new Date(item.scheduled_at) <= now))],
  ];

  async function contentAction(item, action, payload = {}) {
    setBusy(`${item.id}:${action}`);
    try {
      await api.post(`/api/content/${item.id}/${action}`, payload);
      setMessage({ type: 'success', text: action === 'publish' ? 'Publishing completed and was logged.' : 'Content updated.' });
      await load();
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || `Could not ${action} content.` });
    } finally {
      setBusy(null);
    }
  }

  async function generate(event) {
    event.preventDefault();
    setBusy('generate');
    try {
      const response = await api.post(`/api/properties/${generateForm.property_id}/generate-content`, { date: generateForm.date });
      setMessage({ type: 'success', text: response.data.skipped ? 'The 3 posts and 3 stories already exist for this day.' : 'Generated 3 posts and 3 stories.' });
      setGenerateOpen(false);
      await load();
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Content generation failed.' });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-6 pb-10">
      {message && <div className={`fixed bottom-4 end-4 z-50 px-5 py-3 rounded-lg text-white shadow-lg ${message.type === 'error' ? 'bg-rose-600' : 'bg-emerald-600'}`}>{message.text}</div>}
      <div className="flex flex-wrap justify-between items-center gap-4">
        <div><h2 className="text-2xl font-bold text-slate-800">Content</h2><p className="text-slate-500">Review today, upcoming, and previous posts and stories.</p></div>
        <button onClick={() => setGenerateOpen(true)} className="flex items-center gap-2 bg-indigo-600 text-white px-5 py-2.5 rounded-lg"><Zap size={18} /> Generate content</button>
      </div>
      <div className="bg-white border rounded-xl p-4 flex gap-3">
        <select value={kind} onChange={(event) => setKind(event.target.value)} className="border rounded-lg px-3 py-2"><option value="">Posts &amp; stories</option><option value="post">Posts</option><option value="story">Stories</option></select>
        <select value={status} onChange={(event) => setStatus(event.target.value)} className="border rounded-lg px-3 py-2"><option value="">All statuses</option>{Object.keys(badge).map((value) => <option key={value} value={value}>{value.replace('_', ' ')}</option>)}</select>
      </div>

      {loading ? <div className="h-64 flex items-center justify-center"><RefreshCw className="animate-spin text-indigo-600" size={32} /></div> : sections.map(([label, sectionItems]) => (
        <section key={label} className="space-y-3">
          <h3 className="text-lg font-bold text-slate-800">{label} <span className="text-sm text-slate-400">({sectionItems.length})</span></h3>
          {sectionItems.length === 0 ? (
            <div className="bg-white border rounded-xl p-8 text-center text-slate-400"><FileText className="mx-auto mb-2" />No content in this section.</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-5">
              {sectionItems.map((item) => {
                const ready = item.media_url && item.generation_status !== 'FAILED';
                return (
                  <article key={item.id} className="bg-white border rounded-xl overflow-hidden shadow-sm flex flex-col">
                    <button onClick={() => setSelected(item)} className={`${item.kind === 'story' ? 'aspect-[9/12]' : 'aspect-[4/3]'} bg-slate-100 overflow-hidden`}>
                      <MediaPreview src={item.media_url || item.image_path} mediaType={item.media_type} status={item.media_generation_status || 'PENDING'} alt={item.title || 'Content media'} />
                    </button>
                    <div className="p-4 flex-1 space-y-3">
                      <div className="flex justify-between gap-2"><div><p className="font-semibold">{item.title || `${item.kind} variant ${item.variant_number || ''}`}</p><p className="text-xs text-slate-500">{propertyNames[item.property_id]} · {item.platform}</p></div><span className={`text-xs px-2 py-1 rounded h-fit ${badge[item.status] || badge.draft}`}>{item.status}</span></div>
                      {item.kind === 'story' && <div className="text-sm"><strong>{item.story_hook}</strong><p>{item.story_message}</p><span className="text-xs text-slate-400">10-second vertical video</span></div>}
                      {item.kind === 'post' && <p className="text-sm text-slate-700 line-clamp-4">{item.caption}</p>}
                      {item.hashtags && <p className="text-xs text-indigo-600 line-clamp-2">{Array.isArray(item.hashtags) ? item.hashtags.join(' ') : item.hashtags}</p>}
                    </div>
                    {item.approval_status !== 'REJECTED' && item.publish_status === 'DRAFT' && (
                      <div className="grid grid-cols-3 gap-2 p-3 border-t bg-slate-50">
                        <button disabled={!ready || busy?.startsWith(`${item.id}:`)} onClick={() => contentAction(item, 'publish')} className="text-xs bg-indigo-600 text-white rounded-lg py-2 disabled:opacity-40 flex flex-col items-center"><UploadCloud size={15} />Post</button>
                        <button disabled={!ready || busy?.startsWith(`${item.id}:`)} onClick={() => { setScheduleItem(item); setScheduleForm({ scheduled_at: '', platform: item.platform || 'instagram' }); }} className="text-xs bg-emerald-600 text-white rounded-lg py-2 disabled:opacity-40 flex flex-col items-center"><CalendarClock size={15} />Schedule</button>
                        <button disabled={busy?.startsWith(`${item.id}:`)} onClick={() => contentAction(item, 'reject', { reason: window.prompt('Optional rejection reason:') || '' })} className="text-xs border border-rose-200 text-rose-700 rounded-lg py-2 flex flex-col items-center"><X size={15} />Reject</button>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      ))}

      {selected && <ContentDrawer item={selected} properties={propertyNames} onClose={() => setSelected(null)} onUpdate={load} />}

      {generateOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <form onSubmit={generate} className="bg-white rounded-xl p-6 w-full max-w-md space-y-4">
            <div className="flex justify-between"><h3 className="font-bold text-lg">Generate 3 posts + 3 stories</h3><button type="button" onClick={() => setGenerateOpen(false)}><X /></button></div>
            <select required value={generateForm.property_id} onChange={(event) => setGenerateForm({ ...generateForm, property_id: event.target.value })} className="w-full border rounded-lg p-2"><option value="">Select an approved property</option>{properties.filter((property) => property.approval_status === 'APPROVED').map((property) => <option key={property.id} value={property.id}>{property.name}</option>)}</select>
            <input type="date" required value={generateForm.date} onChange={(event) => setGenerateForm({ ...generateForm, date: event.target.value })} className="w-full border rounded-lg p-2" />
            <button disabled={busy === 'generate'} className="w-full bg-indigo-600 text-white rounded-lg py-2 disabled:opacity-50">{busy === 'generate' ? 'Generating…' : 'Generate'}</button>
          </form>
        </div>
      )}

      {scheduleItem && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <form onSubmit={async (event) => { event.preventDefault(); await contentAction(scheduleItem, 'schedule', scheduleForm); setScheduleItem(null); }} className="bg-white rounded-xl p-6 w-full max-w-md space-y-4">
            <h3 className="font-bold text-lg">Approve &amp; Schedule</h3>
            <input type="datetime-local" required value={scheduleForm.scheduled_at} onChange={(event) => setScheduleForm({ ...scheduleForm, scheduled_at: event.target.value })} className="w-full border rounded-lg p-2" />
            <select value={scheduleForm.platform} onChange={(event) => setScheduleForm({ ...scheduleForm, platform: event.target.value })} className="w-full border rounded-lg p-2">{['instagram', 'facebook', 'tiktok', 'x', 'telegram'].map((platform) => <option key={platform}>{platform}</option>)}</select>
            <div className="flex justify-end gap-2"><button type="button" onClick={() => setScheduleItem(null)} className="px-4 py-2 bg-slate-100 rounded-lg">Cancel</button><button className="px-4 py-2 bg-emerald-600 text-white rounded-lg">Schedule</button></div>
          </form>
        </div>
      )}
    </div>
  );
}
