import React, { useState, useEffect } from 'react';
import { 
  Check, X, RefreshCw, CalendarClock, Edit, Image as ImageIcon, 
  ChevronDown, ChevronUp, AlertCircle, Save 
} from 'lucide-react';
import { useLanguage } from '../lib/LanguageContext';
import api from '../lib/api';

export default function Approvals() {
  const [items, setItems] = useState([]);
  const [properties, setProperties] = useState({});
  const [approvalMode, setApprovalMode] = useState('manual');
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [expandedIssues, setExpandedIssues] = useState({});
  const [editStates, setEditStates] = useState({});
  
  const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchInitialData();
  }, []);

  const fetchInitialData = async () => {
    setLoading(true);
    try {
      const [propsRes, settingsRes, pendingRes, approvedRes] = await Promise.all([
        api.get('/api/properties'),
        api.get('/api/settings'),
        api.get('/api/content', { params: { status: 'pending_approval' } }),
        api.get('/api/content', { params: { status: 'approved' } })
      ]);
      
      const propMap = {};
      propsRes.data.forEach(p => propMap[p.id] = p.name);
      setProperties(propMap);
      
      const mode = settingsRes.data.approval_mode;
      if (mode) setApprovalMode(mode);
      
      setItems([...pendingRes.data, ...approvedRes.data]);
    } catch (err) {
      showToast('שגיאה בטעינת נתונים', 'error');
    } finally {
      setLoading(false);
    }
  };

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const handleModeToggle = async () => {
    const newMode = approvalMode === 'manual' ? 'auto' : 'manual';
    const oldMode = approvalMode;
    setApprovalMode(newMode);
    
    try {
      await api.put('/api/settings', { approval_mode: newMode });
      showToast('מצב אישור עודכן');
    } catch (err) {
      setApprovalMode(oldMode);
      showToast('שגיאה בעדכון מצב', 'error');
    }
  };

  const updateItemLocally = (id, changes) => {
    setItems(prev => prev.map(i => i.id === id ? { ...i, ...changes } : i));
  };

  const executeAction = async (id, action, optimisticChanges) => {
    const previousItems = [...items];
    updateItemLocally(id, optimisticChanges);
    
    try {
      const res = await api.post(`/api/content/${id}/${action}`);
      if (res.data?.new_status) {
        updateItemLocally(id, { status: res.data.new_status });
      }
      
      // if regenerate or reject, we might want to remove it from the list if it's no longer pending/approved
      if (action === 'reject' || action === 'regenerate' || action === 'schedule') {
        setTimeout(() => {
          setItems(prev => prev.filter(i => i.id !== id));
        }, 800);
      }
      
    } catch (err) {
      setItems(previousItems);
      showToast(err.response?.data?.detail || 'שגיאה בביצוע פעולה', 'error');
    }
  };

  const saveEdit = async (id) => {
    const editData = editStates[id];
    if (!editData) return;
    
    const previousItems = [...items];
    const optimisticItem = items.find(i => i.id === id);
    updateItemLocally(id, { 
      caption: editData.caption, 
      hashtags: editData.hashtags, 
      // If it was approved, editing makes it pending
      status: optimisticItem.status === 'approved' ? 'pending_approval' : optimisticItem.status 
    });
    
    try {
      const res = await api.patch(`/api/content/${id}`, {
        caption: editData.caption,
        hashtags: editData.hashtags
      });
      updateItemLocally(id, res.data);
      
      const newEditStates = { ...editStates };
      delete newEditStates[id];
      setEditStates(newEditStates);
      
      showToast('נשמר בהצלחה');
    } catch (err) {
      setItems(previousItems);
      showToast(err.response?.data?.detail || 'שגיאה בשמירה', 'error');
    }
  };

  const handleBulk = async (action, targetStatus) => {
    const targetItems = items.filter(i => i.status === targetStatus);
    if (targetItems.length === 0) return;
    
    let success = 0;
    let fail = 0;
    
    for (const item of targetItems) {
      try {
        await api.post(`/api/content/${item.id}/${action}`);
        success++;
        setItems(prev => prev.filter(i => i.id !== item.id)); // remove from view
      } catch (e) {
        fail++;
      }
    }
    
    if (fail > 0) showToast(`הצליחו ${success}, נכשלו ${fail}`, 'error');
    else showToast(`כל הפעולות (${success}) בוצעו בהצלחה`);
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="animate-spin text-indigo-600" size={32} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto pb-10">
      {toast && (
        <div className={`fixed bottom-4 end-4 px-6 py-3 rounded-lg shadow-lg text-white ${toast.type === 'error' ? 'bg-red-500' : 'bg-emerald-500'} z-50 transition-all`}>
          {toast.msg}
        </div>
      )}

      {/* Top Bar */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100 flex flex-wrap justify-between items-center gap-4 sticky top-16 z-20">
        <div>
          <h2 className="text-xl font-bold text-slate-800">מרכז אישורים</h2>
          <p className="text-slate-500 text-sm">אשר, ערוך או תזמן תוכן שממתין לפרסום</p>
        </div>
        
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-lg border border-slate-200">
            <span className="text-sm font-medium text-slate-700">מצב אישור:</span>
            <button 
              onClick={handleModeToggle}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${approvalMode === 'auto' ? 'bg-emerald-500' : 'bg-slate-300'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${approvalMode === 'auto' ? '-translate-x-1' : '-translate-x-6'}`} />
            </button>
            <span className={`text-xs font-bold ${approvalMode === 'auto' ? 'text-emerald-600' : 'text-slate-500'}`}>
              {approvalMode === 'auto' ? 'אוטומטי' : 'ידני'}
            </span>
          </div>
          
          <div className="flex gap-2">
            <button 
              onClick={() => handleBulk('approve', 'pending_approval')}
              className="flex items-center gap-2 bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              <Check size={16} /> אשר הכל
            </button>
            <button 
              onClick={() => handleBulk('schedule', 'approved')}
              className="flex items-center gap-2 bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              <CalendarClock size={16} /> תזמן הכל
            </button>
          </div>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-12 text-center text-slate-400">
          <Check size={48} className="mx-auto mb-4 opacity-50 text-emerald-500" />
          <p className="text-lg font-medium text-slate-600">אין פריטים הממתינים לאישור או תזמון</p>
          <p className="text-sm mt-1">איזה יופי! הכל טופל.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {items.map(item => {
            const isEditing = !!editStates[item.id];
            const aspectClass = item.kind === 'story' ? 'aspect-[9/16] w-2/3 mx-auto' : 'aspect-[4/5] w-full';
            const isApproved = item.status === 'approved';
            
            return (
              <div key={item.id} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col transition-all">
                {/* Header */}
                <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-start">
                  <div>
                    <h3 className="font-bold text-slate-800 text-lg leading-tight mb-1">
                      {properties[item.property_id] || `נכס #${item.property_id}`}
                    </h3>
                    <div className="flex gap-2">
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-indigo-100 text-indigo-700 capitalize">
                        {item.platform}
                      </span>
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-200 text-slate-700 uppercase">
                        {item.language}
                      </span>
                      {isApproved && (
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-700 flex items-center gap-1">
                          <Check size={12} /> מאושר
                        </span>
                      )}
                    </div>
                  </div>
                  {/* Review Score */}
                  <div className={`flex flex-col items-center justify-center w-10 h-10 rounded-full font-bold text-sm ${item.review_score >= 85 ? 'bg-emerald-100 text-emerald-700' : item.review_score >= 70 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                    {item.review_score || '-'}
                  </div>
                </div>
                
                {/* Image */}
                <div className={`bg-slate-100 relative ${aspectClass} overflow-hidden border-b border-slate-100 flex items-center justify-center`}>
                  {item.image_path ? (
                    <img 
                      src={`${BASE_URL}/media/${item.image_path.replace(/^\/+/, '')}`} 
                      alt="Preview" 
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="text-slate-400 flex flex-col items-center gap-2">
                      <ImageIcon size={32} />
                      <span className="text-sm font-medium">אין תמונה</span>
                    </div>
                  )}
                  <div className="absolute bottom-2 end-2 bg-black/60 backdrop-blur-sm text-white px-2 py-1 rounded text-xs font-medium">
                    {item.kind === 'story' ? t('story') : t('post')}
                  </div>
                </div>

                {/* Content */}
                <div className="p-4 flex-1 flex flex-col gap-3">
                  {isEditing ? (
                    <div className="flex flex-col gap-2">
                      <textarea
                        value={editStates[item.id].caption}
                        onChange={e => setEditStates({...editStates, [item.id]: {...editStates[item.id], caption: e.target.value}})}
                        className="w-full border border-slate-300 rounded p-2 text-sm focus:ring-1 focus:ring-indigo-500 min-h-[100px] bg-indigo-50/30"
                      />
                      <input
                        value={editStates[item.id].hashtags}
                        onChange={e => setEditStates({...editStates, [item.id]: {...editStates[item.id], hashtags: e.target.value}})}
                        className="w-full border border-slate-300 rounded p-2 text-sm focus:ring-1 focus:ring-indigo-500 bg-indigo-50/30"
                        placeholder="#האשטאגים"
                      />
                      <div className="flex justify-end gap-2 mt-1">
                        <button 
                          onClick={() => {
                            const newEditStates = {...editStates};
                            delete newEditStates[item.id];
                            setEditStates(newEditStates);
                          }}
                          className="text-slate-500 hover:text-slate-700 text-sm px-2 py-1"
                        >
                          ביטול
                        </button>
                        <button 
                          onClick={() => saveEdit(item.id)}
                          className="bg-indigo-600 text-white text-sm px-3 py-1 rounded hover:bg-indigo-700 flex items-center gap-1"
                        >
                          <Save size={14} /> {t('save')}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="relative group">
                      <p className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed line-clamp-4 group-hover:line-clamp-none transition-all">
                        {item.caption}
                      </p>
                      {item.hashtags && <p className="text-indigo-600 text-sm mt-2 font-medium">{item.hashtags}</p>}
                      <button 
                        onClick={() => setEditStates({
                          ...editStates, 
                          [item.id]: { caption: item.caption, hashtags: item.hashtags || '' }
                        })}
                        className="absolute top-0 end-0 bg-white/90 p-1.5 rounded-full text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Edit size={14} />
                      </button>
                    </div>
                  )}

                  {/* Review Issues Expander */}
                  {item.review_notes && (
                    <div className="mt-auto bg-amber-50 rounded border border-amber-100 overflow-hidden">
                      <button 
                        onClick={() => setExpandedIssues({...expandedIssues, [item.id]: !expandedIssues[item.id]})}
                        className="w-full flex justify-between items-center px-3 py-2 text-xs font-medium text-amber-800 bg-amber-100/50 hover:bg-amber-100 transition-colors"
                      >
                        <span className="flex items-center gap-1.5">
                          <AlertCircle size={14} /> הערות ביקורת ({item.review_score})
                        </span>
                        {expandedIssues[item.id] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                      {expandedIssues[item.id] && (
                        <div className="px-3 py-2 text-xs text-amber-900 border-t border-amber-100 font-mono whitespace-pre-wrap">
                          {(() => {
                            try {
                              const notes = JSON.parse(item.review_notes);
                              if (Array.isArray(notes)) return <ul className="list-disc ps-4">{notes.map((n, i) => <li key={i}>{n}</li>)}</ul>;
                            } catch(e) {}
                            return item.review_notes;
                          })()}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="p-3 bg-slate-50 border-t border-slate-200 grid grid-cols-2 gap-2 shrink-0">
                  {!isApproved ? (
                    <>
                      <button 
                        onClick={() => executeAction(item.id, 'approve', { status: 'approved' })}
                        className="bg-emerald-500 hover:bg-emerald-600 text-white py-2 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1.5"
                      >
                        <Check size={16} /> אשור
                      </button>
                      <button 
                        onClick={() => executeAction(item.id, 'reject', { status: 'rejected' })}
                        className="bg-white border border-slate-300 text-rose-600 hover:bg-rose-50 hover:border-rose-200 py-2 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1.5"
                      >
                        <X size={16} /> דחייה
                      </button>
                    </>
                  ) : (
                    <button 
                      onClick={() => executeAction(item.id, 'schedule', { status: 'scheduled' })}
                      className="col-span-2 bg-purple-600 hover:bg-purple-700 text-white py-2 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1.5"
                    >
                      <CalendarClock size={16} /> תזמן לפרסום
                    </button>
                  )}
                  <button 
                    onClick={() => executeAction(item.id, 'regenerate', { status: 'draft' })}
                    className="col-span-2 bg-slate-200 hover:bg-slate-300 text-slate-700 py-2 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1.5 mt-1"
                  >
                    <RefreshCw size={14} /> {t('regenerate')} (צור מחדש)
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
