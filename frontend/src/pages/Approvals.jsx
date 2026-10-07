import React, { useState, useEffect } from 'react';
import { 
  Check, X, RefreshCw, CalendarClock, Edit,
  ChevronDown, ChevronUp, AlertCircle, Save, UploadCloud, Sparkles
} from 'lucide-react';
import api from '../lib/api';
import MediaPreview from '../components/MediaPreview';

export default function Approvals() {
  const [activeTab, setActiveTab] = useState('content');
  const [items, setItems] = useState([]);
  const [propertiesList, setPropertiesList] = useState([]);
  const [propertiesMap, setPropertiesMap] = useState({});
  const [approvalMode, setApprovalMode] = useState('HUMAN');
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [expandedIssues, setExpandedIssues] = useState({});
  const [editStates, setEditStates] = useState({});
  const [rejectReason, setRejectReason] = useState("");
  const [rejectId, setRejectId] = useState(null);
  const [rejectType, setRejectType] = useState(null); // 'property' or 'content'
  const [scheduleId, setScheduleId] = useState(null);
  const [scheduleForm, setScheduleForm] = useState({ scheduled_at: '', platform: 'instagram' });
  const [busyAction, setBusyAction] = useState(null);

  useEffect(() => {
    fetchInitialData();
  }, [activeTab]);

  const fetchInitialData = async () => {
    setLoading(true);
    try {
      const settingsRes = await api.get('/api/settings');
      const mode = settingsRes.data.approval_mode;
      if (mode) setApprovalMode(mode);

      if (activeTab === 'properties') {
        const propsRes = await api.get('/api/properties');
        setPropertiesList(propsRes.data.filter(p => p.approval_status === 'PENDING'));
      } else {
        const [propsRes, pendingRes] = await Promise.all([
          api.get('/api/properties'),
          api.get('/api/content', { params: { approval_status: 'PENDING' } })
        ]);
        
        const propMap = {};
        propsRes.data.forEach(p => propMap[p.id] = p.name);
        setPropertiesMap(propMap);
        setItems(pendingRes.data);
      }
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
    const newMode = approvalMode === 'HUMAN' ? 'AUTOMATION' : 'HUMAN';
    const oldMode = approvalMode;
    setApprovalMode(newMode);
    try {
      await api.put('/api/settings/approval-mode', { mode: newMode });
      showToast('מצב אישור עודכן');
    } catch (err) {
      setApprovalMode(oldMode);
      showToast('שגיאה בעדכון מצב', 'error');
    }
  };

  const executePropertyAction = async (id, action, reason = null) => {
    setBusyAction(`${id}:${action}`);
    try {
      const payload = reason ? { reason } : {};
      await api.post(`/api/properties/${id}/${action}`, payload);
      setPropertiesList(prev => prev.filter(p => p.id !== id));
      showToast('פעולה בוצעה בהצלחה');
    } catch (err) {
      showToast(err.response?.data?.detail || 'שגיאה בביצוע פעולה', 'error');
    } finally {
      setBusyAction(null);
    }
  };

  const executeContentAction = async (id, action, payload = {}) => {
    setBusyAction(`${id}:${action}`);
    try {
      await api.post(`/api/content/${id}/${action}`, payload);
      setItems(prev => prev.filter(i => i.id !== id));
      showToast('פעולה בוצעה בהצלחה');
    } catch (err) {
      showToast(err.response?.data?.detail || 'שגיאה בביצוע פעולה', 'error');
    } finally {
      setBusyAction(null);
    }
  };

  const handleRejectConfirm = () => {
    if (rejectType === 'property') {
      executePropertyAction(rejectId, 'reject', rejectReason);
    } else {
      executeContentAction(rejectId, 'reject', { reason: rejectReason });
    }
    setRejectId(null);
    setRejectReason("");
  };

  const saveEdit = async (id) => {
    const editData = editStates[id];
    if (!editData) return;
    try {
      const res = await api.patch(`/api/content/${id}`, {
        caption: editData.caption,
        hashtags: editData.hashtags
      });
      setItems(prev => prev.map(i => i.id === id ? { ...i, ...res.data } : i));
      const newEditStates = { ...editStates };
      delete newEditStates[id];
      setEditStates(newEditStates);
      showToast('נשמר בהצלחה');
    } catch (err) {
      showToast(err.response?.data?.detail || 'שגיאה בשמירה', 'error');
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto pb-10">
      {toast && (
        <div className={`fixed bottom-4 end-4 px-6 py-3 rounded-lg shadow-lg text-white ${toast.type === 'error' ? 'bg-red-500' : 'bg-emerald-500'} z-50 transition-all`}>
          {toast.msg}
        </div>
      )}

      {/* Reject Modal */}
      {rejectId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-lg font-bold mb-4">דחיית פריט</h3>
            <p className="text-sm text-slate-600 mb-4">מדוע הפריט נדחה? (אופציונלי)</p>
            <textarea 
              value={rejectReason}
              onChange={e => setRejectReason(e.target.value)}
              className="w-full border border-slate-300 rounded p-3 mb-4 min-h-[100px] text-sm"
              placeholder="סיבת דחייה..."
            />
            <div className="flex justify-end gap-3">
              <button 
                onClick={() => setRejectId(null)}
                className="px-4 py-2 text-slate-600 bg-slate-100 hover:bg-slate-200 rounded font-medium"
              >
                ביטול
              </button>
              <button 
                onClick={handleRejectConfirm}
                className="px-4 py-2 text-white bg-rose-600 hover:bg-rose-700 rounded font-medium"
              >
                דחה
              </button>
            </div>
          </div>
        </div>
      )}

      {scheduleId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <form
            className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              await executeContentAction(scheduleId, 'schedule', scheduleForm);
              setScheduleId(null);
            }}
          >
            <h3 className="text-lg font-bold">Approve &amp; Schedule</h3>
            <label className="block text-sm font-medium">Date and time
              <input type="datetime-local" required value={scheduleForm.scheduled_at} onChange={(event) => setScheduleForm({ ...scheduleForm, scheduled_at: event.target.value })} className="mt-1 w-full border rounded-lg p-2" />
            </label>
            <label className="block text-sm font-medium">Platform
              <select value={scheduleForm.platform} onChange={(event) => setScheduleForm({ ...scheduleForm, platform: event.target.value })} className="mt-1 w-full border rounded-lg p-2">
                {['instagram', 'facebook', 'tiktok', 'x', 'telegram'].map((platform) => <option key={platform} value={platform}>{platform}</option>)}
              </select>
            </label>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setScheduleId(null)} className="px-4 py-2 bg-slate-100 rounded-lg">Cancel</button>
              <button type="submit" disabled={busyAction === `${scheduleId}:schedule`} className="px-4 py-2 bg-emerald-600 text-white rounded-lg disabled:opacity-50">{busyAction === `${scheduleId}:schedule` ? 'Scheduling…' : 'Schedule'}</button>
            </div>
          </form>
        </div>
      )}

      {/* Top Bar */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100 flex flex-col md:flex-row justify-between items-center gap-4 sticky top-16 z-20">
        <div>
          <h2 className="text-xl font-bold text-slate-800">מרכז אישורים</h2>
          <p className="text-slate-500 text-sm">אשר, דחה או ערוך נכסים ותוכן</p>
        </div>
        
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex bg-slate-100 p-1 rounded-lg">
            <button 
              onClick={() => setActiveTab('properties')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'properties' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200'}`}
            >
              נכסים
            </button>
            <button 
              onClick={() => setActiveTab('content')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'content' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200'}`}
            >
              תוכן 
            </button>
          </div>

          <div className="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-lg border border-slate-200">
            <span className="text-sm font-medium text-slate-700">מצב אישור:</span>
            <button 
              onClick={handleModeToggle}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${approvalMode === 'AUTOMATION' ? 'bg-emerald-500' : 'bg-slate-300'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${approvalMode === 'AUTOMATION' ? '-translate-x-1' : '-translate-x-6'}`} />
            </button>
            <span className={`text-xs font-bold ${approvalMode === 'AUTOMATION' ? 'text-emerald-600' : 'text-slate-500'}`}>
              {approvalMode === 'AUTOMATION' ? 'אוטומציה' : 'ידני'}
            </span>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <RefreshCw className="animate-spin text-indigo-600" size={32} />
        </div>
      ) : activeTab === 'properties' ? (
        // Properties Tab
        propertiesList.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-12 text-center text-slate-400">
            <Check size={48} className="mx-auto mb-4 opacity-50 text-emerald-500" />
            <p className="text-lg font-medium text-slate-600">אין נכסים הממתינים לאישור</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {propertiesList.map(prop => (
              <div key={prop.id} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
                <div className="h-48 bg-slate-100 relative overflow-hidden">
                  <MediaPreview src={prop.preview_url} status={prop.media_status} alt={prop.name} />
                </div>
                <div className="p-4 flex-1">
                  <h3 className="font-bold text-lg mb-1">{prop.name}</h3>
                  <p className="text-sm text-slate-500 mb-2">{prop.location}</p>
                  <p className="text-sm text-slate-700 line-clamp-3">{prop.description}</p>
                </div>
                <div className="p-3 bg-slate-50 border-t border-slate-200 grid grid-cols-2 gap-2">
                  <button onClick={() => executePropertyAction(prop.id, 'approve')} className="bg-emerald-500 hover:bg-emerald-600 text-white py-2 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1.5">
                    <Check size={16} /> אשר נכס
                  </button>
                  <button onClick={() => { setRejectType('property'); setRejectId(prop.id); }} className="bg-white border border-slate-300 text-rose-600 hover:bg-rose-50 py-2 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1.5">
                    <X size={16} /> דחה נכס
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        // Content Tab
        items.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-12 text-center text-slate-400">
            <Check size={48} className="mx-auto mb-4 opacity-50 text-emerald-500" />
            <p className="text-lg font-medium text-slate-600">אין פריטי תוכן הממתינים לאישור</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {items.map(item => {
              const isEditing = !!editStates[item.id];
              const aspectClass = item.kind === 'story' ? 'aspect-[9/16] w-2/3 mx-auto' : 'aspect-[4/5] w-full';
              
              return (
                <div key={item.id} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col transition-all">
                  {/* Header */}
                  <div className="p-4 border-b border-slate-100 bg-slate-50 flex justify-between items-start">
                    <div>
                      <h3 className="font-bold text-slate-800 text-lg leading-tight mb-1">
                        {propertiesMap[item.property_id] || `נכס #${item.property_id}`}
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-indigo-100 text-indigo-700 capitalize">
                          {item.platform}
                        </span>
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-200 text-slate-700">
                          {item.kind === 'story' ? 'Story' : 'Post'}
                        </span>
                        {item.angle && (
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-700">
                            {item.angle}
                          </span>
                        )}
                        {item.is_ai_generated && (
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-purple-100 text-purple-700 flex items-center gap-1">
                            <Sparkles size={12}/> AI
                          </span>
                        )}
                      </div>
                    </div>
                    {item.review_score && (
                      <div className={`flex items-center justify-center w-10 h-10 rounded-full font-bold text-sm ${item.review_score >= 85 ? 'bg-emerald-100 text-emerald-700' : item.review_score >= 70 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                        {item.review_score}
                      </div>
                    )}
                  </div>
                  
                  {/* Media */}
                  <div className={`bg-slate-900 relative ${aspectClass} overflow-hidden border-b border-slate-100 flex items-center justify-center`}>
                    <MediaPreview src={item.media_url || item.image_path} mediaType={item.media_type} status={item.media_generation_status || 'PENDING'} alt="Content preview" />
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
                          <button onClick={() => { const s = {...editStates}; delete s[item.id]; setEditStates(s); }} className="text-slate-500 text-sm px-2 py-1">ביטול</button>
                          <button onClick={() => saveEdit(item.id)} className="bg-indigo-600 text-white text-sm px-3 py-1 rounded flex items-center gap-1"><Save size={14} /> שמור</button>
                        </div>
                      </div>
                    ) : (
                      <div className="relative group">
                        <p className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed line-clamp-4 group-hover:line-clamp-none transition-all">{item.caption}</p>
                        {item.hashtags && <p className="text-indigo-600 text-sm mt-2 font-medium">{item.hashtags}</p>}
                        <button 
                          onClick={() => setEditStates({...editStates, [item.id]: { caption: item.caption || '', hashtags: item.hashtags || '' }})}
                          className="absolute top-0 end-0 bg-white/90 p-1.5 rounded-full text-slate-400 hover:text-indigo-600 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Edit size={14} />
                        </button>
                      </div>
                    )}

                    {/* Review Notes */}
                    {item.review_notes && (
                      <div className="mt-auto bg-amber-50 rounded border border-amber-100 overflow-hidden">
                        <button onClick={() => setExpandedIssues({...expandedIssues, [item.id]: !expandedIssues[item.id]})} className="w-full flex justify-between items-center px-3 py-2 text-xs font-medium text-amber-800">
                          <span className="flex items-center gap-1.5"><AlertCircle size={14} /> הערות ביקורת</span>
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
                  <div className="p-3 bg-slate-50 border-t border-slate-200 grid grid-cols-3 gap-2 shrink-0">
                    <button 
                      onClick={() => executeContentAction(item.id, 'publish')}
                      disabled={busyAction?.startsWith(`${item.id}:`)}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white py-2 rounded text-xs font-medium flex flex-col items-center justify-center gap-1"
                    >
                      <UploadCloud size={16} /> אשור ופרסם
                    </button>
                    <button 
                      onClick={() => {
                        setScheduleId(item.id);
                        setScheduleForm({ scheduled_at: '', platform: item.platform || 'instagram' });
                      }}
                      disabled={busyAction?.startsWith(`${item.id}:`)}
                      className="bg-emerald-500 hover:bg-emerald-600 text-white py-2 rounded text-xs font-medium flex flex-col items-center justify-center gap-1"
                    >
                      <CalendarClock size={16} /> אשור ותזמן
                    </button>
                    <button 
                      onClick={() => { setRejectType('content'); setRejectId(item.id); }}
                      disabled={busyAction?.startsWith(`${item.id}:`)}
                      className="bg-white border border-slate-300 text-rose-600 hover:bg-rose-50 py-2 rounded text-xs font-medium flex flex-col items-center justify-center gap-1"
                    >
                      <X size={16} /> דחה
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )
      )}
    </div>
  );
}
