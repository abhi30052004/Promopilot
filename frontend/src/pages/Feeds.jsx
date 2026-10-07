import React, { useEffect, useState } from 'react';
import { AlertCircle, CalendarClock, CheckCircle, RefreshCw, RotateCw, ShieldAlert } from 'lucide-react';
import MediaPreview from '../components/MediaPreview';
import api from '../lib/api';

const statuses = ['PUBLISHED', 'SCHEDULED', 'FAILED'];
const platforms = ['', 'instagram', 'facebook', 'tiktok', 'x', 'telegram'];

export default function Feeds() {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState('PUBLISHED');
  const [platform, setPlatform] = useState('');
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(null);
  const [error, setError] = useState('');

  async function load(showSpinner = false) {
    if (showSpinner) setLoading(true);
    try {
      const response = await api.get('/api/feeds', { params: platform ? { platform } : {} });
      setItems(response.data);
      setError('');
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not load publishing feeds.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(true);
    const interval = window.setInterval(() => load(false), 15000);
    return () => window.clearInterval(interval);
  }, [platform]);

  async function retry(item) {
    setRetrying(item.id);
    try {
      await api.post(`/api/content/${item.id}/retry`);
      await load(false);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Retry failed.');
    } finally {
      setRetrying(null);
    }
  }

  const visible = items.filter((item) => item.publish_status === status);

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto pb-10">
      <div className="bg-white p-5 rounded-xl border shadow-sm flex flex-wrap justify-between gap-4">
        <div><h2 className="text-xl font-bold text-slate-800">Publishing feeds</h2><p className="text-sm text-slate-500">Published, scheduled, and failed content from the real database workflow.</p></div>
        <select value={platform} onChange={(event) => setPlatform(event.target.value)} className="border rounded-lg px-3 py-2 capitalize">{platforms.map((value) => <option key={value} value={value}>{value || 'All platforms'}</option>)}</select>
      </div>

      <div className="grid grid-cols-3 gap-2 bg-white border rounded-xl p-2">
        {statuses.map((value) => {
          const count = items.filter((item) => item.publish_status === value).length;
          return <button key={value} onClick={() => setStatus(value)} className={`rounded-lg px-4 py-3 text-sm font-semibold ${status === value ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}>{value} ({count})</button>;
        })}
      </div>

      {error && <div className="bg-rose-50 border border-rose-200 text-rose-700 p-4 rounded-xl flex gap-2"><AlertCircle />{error}</div>}
      {loading ? (
        <div className="h-64 flex items-center justify-center"><RefreshCw className="animate-spin text-indigo-600" size={32} /></div>
      ) : visible.length === 0 ? (
        <div className="bg-white border rounded-xl p-12 text-center text-slate-400">No {status.toLocaleLowerCase()} items.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {visible.map((item) => {
            const log = item.last_publish_log;
            const demo = status === 'PUBLISHED' && (!log?.external_post_id || log.external_post_id.startsWith('demo-'));
            const date = item.publish_status === 'PUBLISHED' ? item.published_at : item.scheduled_at;
            return (
              <article key={item.id} className="bg-white border rounded-xl overflow-hidden shadow-sm flex flex-col">
                <div className={`${item.kind === 'story' ? 'aspect-[9/14]' : 'aspect-[4/3]'} bg-slate-100`}>
                  <MediaPreview src={item.media_url || item.image_path} mediaType={item.media_type} status="COMPLETED" alt={item.title || 'Published content'} />
                </div>
                <div className="p-4 flex-1 space-y-3">
                  <div className="flex justify-between items-start gap-3">
                    <div><h3 className="font-bold text-slate-800">{item.property_name || `Property #${item.property_id}`}</h3><p className="text-xs text-slate-500 capitalize">{item.platform} · {item.kind}</p></div>
                    <span className={`text-xs font-bold px-2 py-1 rounded flex items-center gap-1 ${status === 'PUBLISHED' ? 'bg-emerald-100 text-emerald-700' : status === 'SCHEDULED' ? 'bg-purple-100 text-purple-700' : 'bg-rose-100 text-rose-700'}`}>
                      {status === 'PUBLISHED' ? <CheckCircle size={12} /> : status === 'SCHEDULED' ? <CalendarClock size={12} /> : <AlertCircle size={12} />}{status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap line-clamp-5">{item.caption}</p>
                  {item.hashtags && <p className="text-xs text-indigo-600">{Array.isArray(item.hashtags) ? item.hashtags.join(' ') : item.hashtags}</p>}
                  <p className="text-xs text-slate-400">{date ? new Date(`${date}${date.endsWith?.('Z') ? '' : 'Z'}`).toLocaleString() : 'Time unavailable'}</p>
                  {status === 'PUBLISHED' && (
                    <div className={`text-[11px] rounded px-2 py-1 flex items-center gap-1 w-fit ${demo ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                      <ShieldAlert size={12} />{demo ? 'Demo publisher — no real social API call' : 'Live publisher'}
                    </div>
                  )}
                  {status === 'FAILED' && <p className="text-xs text-rose-700 bg-rose-50 p-2 rounded">{item.publish_error || item.error || 'Publishing failed.'}</p>}
                </div>
                {status === 'FAILED' && <button onClick={() => retry(item)} disabled={retrying === item.id} className="m-3 mt-0 bg-indigo-600 text-white py-2 rounded-lg flex items-center justify-center gap-2 disabled:opacity-50"><RotateCw size={15} className={retrying === item.id ? 'animate-spin' : ''} />Retry</button>}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
