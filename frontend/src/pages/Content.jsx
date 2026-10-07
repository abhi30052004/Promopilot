import React, { useState, useEffect } from 'react';
import { Filter, X, RefreshCw, FileText, Zap, Image as ImageIcon } from 'lucide-react';
import { useLanguage } from '../lib/LanguageContext';
import api from '../lib/api';
import ContentDrawer from '../components/ContentDrawer';

const STATUS_COLORS = {
  draft: 'bg-slate-100 text-slate-700 border-slate-200',
  pending_approval: 'bg-amber-100 text-amber-700 border-amber-200',
  approved: 'bg-blue-100 text-blue-700 border-blue-200',
  scheduled: 'bg-purple-100 text-purple-700 border-purple-200',
  published: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  failed: 'bg-red-100 text-red-700 border-red-200',
  rejected: 'bg-rose-100 text-rose-800 border-rose-200'
};







export default function Content() {
  const { t } = useLanguage();

const STATUS_LABELS = {
  draft: t('draft'),
  pending_approval: t('awaiting_approval'),
  approved: t('approved'),
  scheduled: t('scheduled'),
  published: t('published'),
  failed: t('failed'),
  rejected: t('rejected')
};
const PLATFORM_LABELS = {
  facebook: t('facebook'),
  instagram: t('instagram'),
  tiktok: t('tiktok'),
  x: 'X',
  telegram: t('telegram')
};
const KIND_LABELS = {
  post: t('post'),
  story: t('story')
};
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [properties, setProperties] = useState({});
  const [filters, setFilters] = useState({
    date: '', status: '', platform: '', kind: '', language: ''
  });
  
  const [selectedItem, setSelectedItem] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  
  const [generateConfig, setGenerateConfig] = useState({
    date: new Date().toISOString().split('T')[0],
    mode: 'manual'
  });
  const [isGenerating, setIsGenerating] = useState(false);
  
  // Drawer action states
  const [actionLoading, setActionLoading] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [translation, setTranslation] = useState(null);

  const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchProperties();
  }, []);

  useEffect(() => {
    fetchContent();
  }, [filters]);

  const fetchProperties = async () => {
    try {
      const res = await api.get('/api/properties');
      const propMap = {};
      res.data.forEach(p => propMap[p.id] = p.name);
      setProperties(propMap);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchContent = async () => {
    setLoading(true);
    try {
      // Clean empty filters
      const params = Object.fromEntries(Object.entries(filters).filter(([_, v]) => v !== ''));
      const res = await api.get('/api/content', { params });
      setItems(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    setIsGenerating(true);
    try {
      await api.post('/api/agent/run', generateConfig);
      setIsGenerateModalOpen(false);
      fetchContent();
    } catch (e) {
      alert('שגיאה ביצירת תוכן');
    } finally {
      setIsGenerating(false);
    }
  };

  const openDrawer = (item) => {
    setSelectedItem(item);
    setIsDrawerOpen(true);
  };

  // handleAction was moved to ContentDrawer

  return (
    <div className="flex flex-col gap-6 relative">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">ניהול תוכן</h2>
          <p className="text-slate-500">צפה, ערוך ואשר את התוכן שהמערכת יצרה</p>
        </div>
        <button 
          onClick={() => setIsGenerateModalOpen(true)}
          className="flex items-center gap-2 bg-indigo-600 text-white px-5 py-2.5 rounded-lg hover:bg-indigo-700 transition-colors shadow-sm font-medium cursor-pointer"
        >
          <Zap size={18} />
          <span>ייצר תוכן חדש</span>
        </button>
      </div>

      <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-100 flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2 text-slate-500 pe-2 border-e border-slate-200">
          <Filter size={18} />
          <span className="font-medium text-sm">סינון:</span>
        </div>
        <input 
          type="date" 
          value={filters.date} 
          onChange={e => setFilters({...filters, date: e.target.value})}
          className="border border-slate-200 rounded-md px-3 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
        />
        <select 
          value={filters.status} 
          onChange={e => setFilters({...filters, status: e.target.value})}
          className="border border-slate-200 rounded-md px-3 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none min-w-[120px]"
        >
          <option value="">כל הסטטוסים</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select 
          value={filters.platform} 
          onChange={e => setFilters({...filters, platform: e.target.value})}
          className="border border-slate-200 rounded-md px-3 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none min-w-[120px]"
        >
          <option value="">כל הפלטפורמות</option>
          {Object.entries(PLATFORM_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select 
          value={filters.kind} 
          onChange={e => setFilters({...filters, kind: e.target.value})}
          className="border border-slate-200 rounded-md px-3 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
        >
          <option value="">פוסט / סטורי</option>
          {Object.entries(KIND_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select 
          value={filters.language} 
          onChange={e => setFilters({...filters, language: e.target.value})}
          className="border border-slate-200 rounded-md px-3 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
        >
          <option value="">שפה</option>
          <option value="he">עברית</option>
          <option value="en">אנגלית</option>
        </select>
        
        {Object.values(filters).some(x => x !== '') && (
          <button 
            onClick={() => setFilters({date: '', status: '', platform: '', kind: '', language: ''})}
            className="text-slate-400 hover:text-slate-700 text-sm flex items-center gap-1 ms-auto"
          >
            <X size={14} /> נקה סינון
          </button>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <RefreshCw className="animate-spin text-indigo-600" size={32} />
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col justify-center items-center h-64 text-slate-400">
            <FileText size={48} className="mb-4 opacity-50" />
            <p>לא נמצאו פריטי תוכן</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-start border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-sm">
                  <th className="py-3 px-4 font-medium text-start">תצוגה</th>
                  <th className="py-3 px-4 font-medium text-start">נכס</th>
                  <th className="py-3 px-4 font-medium text-start">סוג</th>
                  <th className="py-3 px-4 font-medium text-start">פלטפורמה</th>
                  <th className="py-3 px-4 font-medium text-start">שפה</th>
                  <th className="py-3 px-4 font-medium text-start">תזמון</th>
                  <th className="py-3 px-4 font-medium text-start">ציון</th>
                  <th className="py-3 px-4 font-medium text-start">סטטוס</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr 
                    key={item.id} 
                    onClick={() => openDrawer(item)}
                    className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4">
                      {item.image_path ? (
                        <div className="w-12 h-12 rounded bg-slate-200 overflow-hidden shadow-sm">
                          <img 
                            src={`${BASE_URL}/media/${item.image_path.replace(/^\/+/, '')}`} 
                            alt="thumbnail" 
                            className="w-full h-full object-cover"
                          />
                        </div>
                      ) : (
                        <div className="w-12 h-12 rounded bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-400">
                          <ImageIcon size={20} />
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 text-sm font-medium text-slate-800">
                      {properties[item.property_id] || `נכס #${item.property_id}`}
                    </td>
                    <td className="py-3 px-4 text-sm text-slate-600">
                      {KIND_LABELS[item.kind] || item.kind}
                    </td>
                    <td className="py-3 px-4 text-sm text-slate-600 capitalize">
                      {PLATFORM_LABELS[item.platform] || item.platform}
                    </td>
                    <td className="py-3 px-4 text-sm text-slate-600 uppercase">
                      {item.language}
                    </td>
                    <td className="py-3 px-4 text-sm text-slate-600 dir-ltr text-start">
                      {item.scheduled_at ? new Date(item.scheduled_at).toLocaleString('he-IL', {
                        month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
                      }) : '-'}
                    </td>
                    <td className="py-3 px-4 text-sm">
                      {item.review_score !== null ? (
                        <span className={`font-semibold ${item.review_score >= 85 ? 'text-emerald-600' : item.review_score >= 70 ? 'text-amber-600' : 'text-red-600'}`}>
                          {item.review_score}
                        </span>
                      ) : <span className="text-slate-400">-</span>}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${STATUS_COLORS[item.status] || STATUS_COLORS.draft}`}>
                        {STATUS_LABELS[item.status] || item.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {isDrawerOpen && selectedItem && (
        <ContentDrawer 
          item={selectedItem} 
          properties={properties} 
          onClose={() => setIsDrawerOpen(false)} 
          onUpdate={fetchContent} 
        />
      )}

      {isGenerateModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2">
                <Zap size={18} className="text-indigo-600" />
                יצירת תוכן חדש (Agent)
              </h3>
              <button onClick={() => !isGenerating && setIsGenerateModalOpen(false)} className="text-slate-400 hover:text-slate-700">
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleGenerate} className="p-6 flex flex-col gap-5">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">תאריך יעד</label>
                <input 
                  type="date"
                  required
                  value={generateConfig.date}
                  onChange={e => setGenerateConfig({...generateConfig, date: e.target.value})}
                  className="w-full border border-slate-200 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                  disabled={isGenerating}
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">מצב אישור</label>
                <div className="grid grid-cols-2 gap-3">
                  <label className={`border rounded-lg p-3 flex flex-col items-center gap-1 cursor-pointer transition-colors ${generateConfig.mode === 'manual' ? 'bg-indigo-50 border-indigo-200 text-indigo-700' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                    <input type="radio" name="mode" className="sr-only" checked={generateConfig.mode === 'manual'} onChange={() => setGenerateConfig({...generateConfig, mode: 'manual'})} disabled={isGenerating} />
                    <span className="font-medium text-sm">ידני</span>
                    <span className="text-xs opacity-70">דורש אישור לכל פוסט</span>
                  </label>
                  <label className={`border rounded-lg p-3 flex flex-col items-center gap-1 cursor-pointer transition-colors ${generateConfig.mode === 'auto' ? 'bg-indigo-50 border-indigo-200 text-indigo-700' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                    <input type="radio" name="mode" className="sr-only" checked={generateConfig.mode === 'auto'} onChange={() => setGenerateConfig({...generateConfig, mode: 'auto'})} disabled={isGenerating} />
                    <span className="font-medium text-sm">אוטומטי</span>
                    <span className="text-xs opacity-70">מתזמן ישירות אם עבר</span>
                  </label>
                </div>
              </div>
              
              <div className="mt-2 flex justify-end gap-3">
                <button 
                  type="button" 
                  onClick={() => setIsGenerateModalOpen(false)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg font-medium transition-colors"
                  disabled={isGenerating}
                >
                  ביטול
                </button>
                <button 
                  type="submit"
                  disabled={isGenerating}
                  className="px-6 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors shadow-sm flex items-center gap-2 disabled:opacity-70"
                >
                  {isGenerating ? (
                    <>
                      <RefreshCw size={18} className="animate-spin" />
                      מייצר... (קח דקה)
                    </>
                  ) : (
                    'הפעל סוכן'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
