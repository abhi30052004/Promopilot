import React, { useState, useEffect } from 'react';
import { RefreshCw, MapPin, Search } from 'lucide-react';
import api from '../lib/api';

export default function Properties() {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    fetchProperties();
  }, []);

  const fetchProperties = async () => {
    try {
      const res = await api.get('/api/properties');
      setProperties(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filtered = properties.filter(p => p.name.includes(search) || (p.location && p.location.includes(search)));

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="animate-spin text-indigo-600"><RefreshCw size={32} /></div>
      </div>
    );
  }

  const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border border-slate-100">
        <div>
          <h2 className="text-xl font-bold text-slate-800">נכסים</h2>
          <p className="text-slate-500 text-sm">נהל את רשימת הנכסים שנשאבו מהאתר</p>
        </div>
        <div className="relative">
          <Search size={18} className="absolute start-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input 
            type="text" 
            placeholder="חיפוש נכס..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ps-10 pe-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 w-64"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-12 text-center">
          <p className="text-slate-500 mb-4">לא נמצאו נכסים</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map(prop => (
            <div key={prop.id} className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden hover:shadow-md transition-shadow group flex flex-col">
              <div className="h-48 bg-slate-100 relative overflow-hidden">
                {prop.images && prop.images.length > 0 ? (
                  <img 
                    src={`${BASE_URL}/media/${prop.images[0].replace(/^\/+/, '')}`} 
                    alt={prop.name}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-400 bg-slate-200">
                    אין תמונה
                  </div>
                )}
                <div className="absolute top-3 end-3 bg-white/90 backdrop-blur px-3 py-1 rounded-full text-xs font-semibold text-slate-700 shadow-sm">
                  {prop.type === 'villa' ? 'וילה' : prop.type === 'cabin' ? 'צימר' : prop.type || 'נכס'}
                </div>
              </div>
              <div className="p-5 flex-1 flex flex-col">
                <h3 className="font-bold text-lg text-slate-800 mb-2 truncate" title={prop.name}>{prop.name}</h3>
                <div className="flex items-center gap-2 text-slate-500 text-sm mb-4">
                  <MapPin size={16} />
                  <span>{prop.location || 'לא צוין מיקום'}</span>
                </div>
                <div className="mt-auto flex justify-between items-center text-xs">
                  <span className="text-slate-400">
                    עודכן: {prop.last_synced_at ? new Date(prop.last_synced_at).toLocaleDateString('he-IL') : 'לא ידוע'}
                  </span>
                  {prop.url && (
                    <a href={prop.url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:text-indigo-800 font-medium">
                      צפה באתר
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
