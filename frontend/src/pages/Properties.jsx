import React, { useEffect, useMemo, useState } from 'react';
import {
  CheckCircle, ExternalLink, MapPin, RefreshCw, Search,
  Sparkles, X,
} from 'lucide-react';
import MediaPreview from '../components/MediaPreview';
import api from '../lib/api';

const statusStyle = {
  APPROVED: 'bg-emerald-100 text-emerald-700',
  REJECTED: 'bg-rose-100 text-rose-700',
  PENDING: 'bg-amber-100 text-amber-700',
};

export default function Properties() {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [message, setMessage] = useState(null);

  async function fetchProperties() {
    setLoading(true);
    try {
      const response = await api.get('/api/properties');
      setProperties(response.data);
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Could not load properties.' });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchProperties(); }, []);

  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    if (!term) return properties;
    return properties.filter((property) =>
      `${property.name || ''} ${property.location || ''}`.toLocaleLowerCase().includes(term));
  }, [properties, search]);

  async function openDetails(id) {
    setDetailLoading(true);
    setSelected({ id });
    try {
      const response = await api.get(`/api/properties/${id}`);
      setSelected(response.data);
    } catch (error) {
      setSelected(null);
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Could not load property details.' });
    } finally {
      setDetailLoading(false);
    }
  }

  async function act(property, action) {
    let body = {};
    if (action === 'reject') {
      if (!window.confirm(`Reject ${property.name}?`)) return;
      const reason = window.prompt('Optional rejection reason:') || '';
      body = { reason };
    } else if (action === 'approve' && !window.confirm(`Approve ${property.name} and start content generation?`)) {
      return;
    }
    setBusy(`${property.id}:${action}`);
    try {
      await api.post(`/api/properties/${property.id}/${action}`, body);
      setMessage({ type: 'success', text: action === 'approve' ? 'Property approved. Media and content generation started.' : 'Property rejected.' });
      await fetchProperties();
      if (selected?.id === property.id) await openDetails(property.id);
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || `Could not ${action} property.` });
    } finally {
      setBusy(null);
    }
  }

  async function generate(property) {
    setBusy(`${property.id}:generate`);
    try {
      const response = await api.post(`/api/properties/${property.id}/generate-content`, {});
      setMessage({
        type: 'success',
        text: response.data.skipped ? 'Content already exists for today.' : 'Content generation completed or was queued.',
      });
      await fetchProperties();
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Content generation failed.' });
    } finally {
      setBusy(null);
    }
  }

  async function retryMedia(property) {
    setBusy(`${property.id}:media`);
    try {
      await api.post(`/api/properties/${property.id}/validate-images`);
      setMessage({ type: 'success', text: 'Image validation and replacement generation started.' });
      await fetchProperties();
      if (selected?.id === property.id) await openDetails(property.id);
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Could not retry property media.' });
    } finally {
      setBusy(null);
    }
  }

  async function sync() {
    const url = window.prompt('Website URL to scrape:', 'https://tzelahahar.co.il/');
    if (!url) return;
    setBusy('sync');
    try {
      const response = await api.post('/api/properties/sync', { url });
      setMessage({ type: 'success', text: `Scrape complete: ${response.data.results.created} created, ${response.data.results.updated} updated.` });
      await fetchProperties();
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Website scrape failed.' });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto pb-10">
      {message && (
        <div className={`fixed bottom-4 end-4 z-50 px-5 py-3 rounded-lg text-white shadow-lg ${message.type === 'error' ? 'bg-rose-600' : 'bg-emerald-600'}`}>
          {message.text}
        </div>
      )}

      <div className="flex flex-wrap justify-between items-center gap-4 bg-white p-6 rounded-xl shadow-sm border border-slate-100">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Properties</h2>
          <p className="text-slate-500 text-sm">Review scraped properties and their media.</p>
        </div>
        <div className="flex gap-3">
          <div className="relative">
            <Search size={18} className="absolute start-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search properties" className="ps-10 pe-4 py-2 border border-slate-200 rounded-lg w-64" />
          </div>
          <button onClick={sync} disabled={busy === 'sync'} className="px-4 py-2 rounded-lg bg-indigo-600 text-white flex items-center gap-2 disabled:opacity-60">
            <RefreshCw size={16} className={busy === 'sync' ? 'animate-spin' : ''} /> Sync website
          </button>
        </div>
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center"><RefreshCw className="animate-spin text-indigo-600" size={32} /></div>
      ) : filtered.length === 0 ? (
        <div className="bg-white rounded-xl border p-12 text-center text-slate-500">No properties found.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((property) => (
            <article key={property.id} className="bg-white rounded-xl border border-slate-100 overflow-hidden shadow-sm flex flex-col">
              <button onClick={() => openDetails(property.id)} className="h-48 bg-slate-100 text-start overflow-hidden">
                <MediaPreview
                  src={property.preview_url}
                  status={property.media_status}
                  alt={property.name}
                  fallbackText={property.media_status === 'FAILED' ? 'Image unavailable — replacement generation failed' : undefined}
                />
              </button>
              <div className="p-5 flex-1 flex flex-col gap-3">
                <div className="flex justify-between gap-3">
                  <h3 className="font-bold text-lg text-slate-800">{property.name}</h3>
                  <span className={`px-2 py-1 rounded-full text-xs font-semibold h-fit ${statusStyle[property.approval_status] || statusStyle.PENDING}`}>
                    {property.approval_status || 'PENDING'}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-slate-500 text-sm"><MapPin size={15} />{property.location || 'Location not supplied'}</div>
                <p className="text-sm text-slate-600 line-clamp-3">{property.description || 'No description supplied.'}</p>
                <div className="mt-auto flex flex-wrap gap-2 pt-2">
                  {property.approval_status === 'PENDING' && (
                    <>
                      <button onClick={() => act(property, 'approve')} disabled={busy?.startsWith(`${property.id}:`)} className="flex-1 bg-emerald-600 text-white py-2 rounded-lg text-sm flex justify-center items-center gap-1 disabled:opacity-50">
                        {busy === `${property.id}:approve` ? <RefreshCw size={15} className="animate-spin" /> : <CheckCircle size={15} />} Approve
                      </button>
                      <button onClick={() => act(property, 'reject')} disabled={busy?.startsWith(`${property.id}:`)} className="flex-1 border border-rose-200 text-rose-700 py-2 rounded-lg text-sm">Reject</button>
                    </>
                  )}
                  {property.approval_status === 'APPROVED' && (
                    <button onClick={() => generate(property)} disabled={busy?.startsWith(`${property.id}:`)} className="flex-1 bg-indigo-600 text-white py-2 rounded-lg text-sm flex justify-center items-center gap-1 disabled:opacity-50">
                      <Sparkles size={15} /> Generate content
                    </button>
                  )}
                  {property.media_status === 'FAILED' && (
                    <button onClick={() => retryMedia(property)} disabled={busy?.startsWith(`${property.id}:`)} className="flex-1 border border-amber-300 text-amber-800 py-2 rounded-lg text-sm flex justify-center items-center gap-1 disabled:opacity-50">
                      <RefreshCw size={15} className={busy === `${property.id}:media` ? 'animate-spin' : ''} /> Retry image
                    </button>
                  )}
                  <button onClick={() => openDetails(property.id)} className="px-3 py-2 border rounded-lg text-sm">Details</button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 bg-slate-950/50 flex items-center justify-center p-4" onMouseDown={() => setSelected(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto" onMouseDown={(event) => event.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b p-5 flex justify-between items-center z-10">
              <div><h3 className="font-bold text-xl">{selected.name || 'Property details'}</h3><p className="text-sm text-slate-500">Status: {selected.approval_status || 'Loading…'}</p></div>
              <button onClick={() => setSelected(null)}><X /></button>
            </div>
            {detailLoading || !selected.name ? (
              <div className="h-64 flex items-center justify-center"><RefreshCw className="animate-spin" /></div>
            ) : (
              <div className="p-6 grid md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div><span className="text-xs uppercase text-slate-400">Location</span><p>{selected.location || 'Not supplied'}</p></div>
                  <div><span className="text-xs uppercase text-slate-400">Price</span><p>{selected.price || 'Not supplied'}</p></div>
                  <div><span className="text-xs uppercase text-slate-400">Description</span><p className="text-sm whitespace-pre-wrap">{selected.description || 'Not supplied'}</p></div>
                  <div><span className="text-xs uppercase text-slate-400">Amenities</span><p className="text-sm">{Array.isArray(selected.amenities) ? selected.amenities.join(', ') : selected.amenities || 'Not supplied'}</p></div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="bg-slate-100 px-2 py-1 rounded">Media: {selected.media_status}</span>
                    <span className="bg-slate-100 px-2 py-1 rounded">Content: {selected.content_generation_status}</span>
                  </div>
                  {selected.media_status === 'FAILED' && (
                    <button onClick={() => retryMedia(selected)} disabled={busy === `${selected.id}:media`} className="px-3 py-2 rounded-lg border border-amber-300 text-amber-800 text-sm flex items-center gap-2 disabled:opacity-50">
                      <RefreshCw size={15} className={busy === `${selected.id}:media` ? 'animate-spin' : ''} /> Retry image generation
                    </button>
                  )}
                  {(selected.source_url || selected.url) && <a href={selected.source_url || selected.url} target="_blank" rel="noreferrer" className="text-indigo-600 text-sm flex items-center gap-1"><ExternalLink size={14} /> Open source website</a>}
                </div>
                <div>
                  <h4 className="font-semibold mb-3">Original and replacement media</h4>
                  <div className="grid grid-cols-2 gap-3">
                    {(selected.property_images || []).map((image) => (
                      <div key={image.id} className="aspect-square rounded-lg overflow-hidden border relative">
                        <MediaPreview src={image.media_url} status={image.media_url ? 'COMPLETED' : selected.media_status} alt={selected.name} />
                        <span className="absolute bottom-2 start-2 bg-black/70 text-white text-[10px] px-2 py-1 rounded">{image.is_ai_generated ? 'AI replacement' : image.status === 'VALID' ? 'Original' : 'Unavailable'}</span>
                      </div>
                    ))}
                    {(selected.property_images || []).length === 0 && <div className="col-span-2 aspect-video"><MediaPreview status={selected.media_status} /></div>}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
