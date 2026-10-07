import React, { useState } from 'react';
import { 
  X, RefreshCw, Edit, Image as ImageIcon, Check, CalendarClock, 
  CheckSquare, Globe, MessageSquare 
} from 'lucide-react';
import { useLanguage } from '../lib/LanguageContext';
import api from '../lib/api';
import MediaPreview from './MediaPreview';

const STATUS_COLORS = {
  draft: 'bg-slate-100 text-slate-700 border-slate-200',
  pending_approval: 'bg-amber-100 text-amber-700 border-amber-200',
  approved: 'bg-blue-100 text-blue-700 border-blue-200',
  scheduled: 'bg-purple-100 text-purple-700 border-purple-200',
  published: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  failed: 'bg-red-100 text-red-700 border-red-200',
  rejected: 'bg-rose-100 text-rose-800 border-rose-200'
};

export default function ContentDrawer({ item: initialItem, properties, onClose, onUpdate }) {
  const { t } = useLanguage();
  const [item, setItem] = useState(initialItem);
  const [actionLoading, setActionLoading] = useState(null);

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
  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState({
    caption: initialItem.caption || '',
    hashtags: initialItem.hashtags || '',
    cta: initialItem.cta || '',
    scheduled_at: initialItem.scheduled_at || ''
  });
  const [translation, setTranslation] = useState(null);

  const handleAction = async (action, endpoint, method = 'post', data = {}) => {
    setActionLoading(action);
    try {
      if (action === 'translate') {
        const res = await api.post(endpoint, data);
        setTranslation(res.data.translated);
      } else if (method === 'post') {
        await api.post(endpoint, data);
        const updatedRes = await api.get(`/api/content/${item.id}`);
        setItem(updatedRes.data);
        if (onUpdate) onUpdate();
      } else if (method === 'patch') {
        const res = await api.patch(endpoint, data);
        setItem(res.data);
        setEditMode(false);
        if (onUpdate) onUpdate();
      }
    } catch (e) {
      alert(e.response?.data?.detail || 'שגיאה בביצוע פעולה');
    } finally {
      setActionLoading(null);
    }
  };

  if (!item) return null;

  return (
    <>
      <div 
        className="fixed inset-0 bg-slate-900/20 backdrop-blur-sm z-40" 
        onClick={onClose}
      />
      
      <div className="fixed inset-y-0 end-0 w-full max-w-xl bg-white shadow-2xl z-50 flex flex-col overflow-hidden border-s border-slate-200 animate-in slide-in-from-end-full duration-300">
        <div className="flex justify-between items-center p-5 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-bold text-slate-800">
              {KIND_LABELS[item.kind]} ל{PLATFORM_LABELS[item.platform]}
            </h3>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${STATUS_COLORS[item.status]}`}>
              {STATUS_LABELS[item.status] || item.status}
            </span>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 bg-white rounded-full p-1 border border-slate-200">
            <X size={18} />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
          <div className={`${item.kind === 'story' ? 'aspect-[9/16] max-h-[600px]' : 'aspect-[4/3]'} rounded-xl overflow-hidden bg-slate-100`}>
            <MediaPreview src={item.media_url || item.image_path} mediaType={item.media_type} status={item.media_generation_status || 'PENDING'} alt="Content media" className="w-full h-full object-contain" />
          </div>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="flex justify-between items-center px-4 py-3 border-b border-slate-100 bg-slate-50">
              <h4 className="font-semibold text-slate-700 flex items-center gap-2">
                <MessageSquare size={16} /> טקסט - {properties[item.property_id]}
              </h4>
              {!editMode && (
                <button onClick={() => setEditMode(true)} className="text-indigo-600 hover:text-indigo-800 text-sm flex items-center gap-1 font-medium">
                  <Edit size={14} /> ערוך
                </button>
              )}
            </div>
            
            <div className="p-4">
              {editMode ? (
                <div className="flex flex-col gap-3">
                  <textarea 
                    value={editForm.caption}
                    onChange={e => setEditForm({...editForm, caption: e.target.value})}
                    className="w-full border border-slate-200 rounded-lg p-3 text-sm focus:ring-1 focus:ring-indigo-500 min-h-[100px]"
                    placeholder="כיתוב..."
                  />
                  <input 
                    value={editForm.hashtags}
                    onChange={e => setEditForm({...editForm, hashtags: e.target.value})}
                    className="w-full border border-slate-200 rounded-lg p-3 text-sm focus:ring-1 focus:ring-indigo-500"
                    placeholder="#האשטגים"
                  />
                  <input 
                    value={editForm.cta}
                    onChange={e => setEditForm({...editForm, cta: e.target.value})}
                    className="w-full border border-slate-200 rounded-lg p-3 text-sm focus:ring-1 focus:ring-indigo-500"
                    placeholder="הנעה לפעולה (CTA)"
                  />
                  <input 
                    type="datetime-local"
                    value={editForm.scheduled_at ? editForm.scheduled_at.substring(0, 16) : ''}
                    onChange={e => setEditForm({...editForm, scheduled_at: e.target.value})}
                    className="w-full border border-slate-200 rounded-lg p-3 text-sm focus:ring-1 focus:ring-indigo-500"
                    dir="ltr"
                  />
                  <div className="flex gap-2 mt-2">
                    <button 
                      onClick={() => handleAction('edit', `/api/content/${item.id}`, 'patch', editForm)}
                      className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 flex-1"
                    >
                      שמור שינויים
                    </button>
                    <button 
                      onClick={() => setEditMode(false)}
                      className="bg-slate-100 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-200 flex-1"
                    >
                      ביטול
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-slate-700 text-sm whitespace-pre-wrap flex flex-col gap-3">
                  <p className="leading-relaxed">{item.caption}</p>
                  {item.cta && <p className="font-medium text-slate-900">{item.cta}</p>}
                  {item.hashtags && <p className="text-indigo-600">{item.hashtags}</p>}
                  {item.link && (
                    <a href={item.link} target="_blank" className="text-slate-500 hover:text-indigo-600 flex items-center gap-1 text-xs bg-slate-50 p-2 rounded border border-slate-100 w-fit">
                      <Globe size={12} /> {item.link}
                    </a>
                  )}
                </div>
              )}
            </div>
          </div>

          {translation && (
            <div className="bg-indigo-50 rounded-xl border border-indigo-100 shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-indigo-100 bg-indigo-100/50">
                <h4 className="font-semibold text-indigo-900 text-sm">תרגום (עותק נפרד במסד הנתונים)</h4>
              </div>
              <div className="p-4 text-slate-700 text-sm whitespace-pre-wrap dir-ltr text-start">
                {translation.caption}
                <br/><br/>
                {translation.cta && <span className="font-medium">{translation.cta}<br/></span>}
                {translation.hashtags && <span className="text-indigo-600">{translation.hashtags}</span>}
              </div>
            </div>
          )}

          {item.review_notes && (
            <div className="bg-amber-50 rounded-xl border border-amber-100 shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-amber-100 bg-amber-100/50 flex justify-between items-center">
                <h4 className="font-semibold text-amber-900 text-sm">הערות בודק אוטומטי (ציון: {item.review_score})</h4>
              </div>
              <div className="p-4 text-amber-800 text-sm whitespace-pre-wrap">
                {(() => {
                  try {
                    const notes = JSON.parse(item.review_notes);
                    if (Array.isArray(notes) && notes.length > 0) {
                      return <ul className="list-disc ps-5 flex flex-col gap-1">{notes.map((n, i) => <li key={i}>{n}</li>)}</ul>;
                    }
                  } catch(e) {}
                  return item.review_notes;
                })()}
              </div>
            </div>
          )}
        </div>
        
        <div className="border-t border-slate-200 p-4 bg-white flex flex-wrap gap-2 shrink-0">
          {item.status === 'pending_approval' && (
            <>
              <button 
                onClick={() => handleAction('approve', `/api/content/${item.id}/approve`)}
                disabled={actionLoading !== null}
                className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors flex justify-center items-center gap-2"
              >
                {actionLoading === 'approve' ? <RefreshCw size={16} className="animate-spin" /> : <Check size={16} />}
                {t('approve')}
              </button>
              <button 
                onClick={() => handleAction('reject', `/api/content/${item.id}/reject`)}
                disabled={actionLoading !== null}
                className="flex-1 bg-rose-100 hover:bg-rose-200 text-rose-700 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors flex justify-center items-center gap-2"
              >
                {actionLoading === 'reject' ? <RefreshCw size={16} className="animate-spin" /> : <X size={16} />}
                {t('reject')}
              </button>
            </>
          )}
          
          {item.status === 'approved' && (
            <button 
              onClick={() => handleAction('schedule', `/api/content/${item.id}/schedule`)}
              disabled={actionLoading !== null}
              className="w-full bg-purple-600 hover:bg-purple-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors flex justify-center items-center gap-2"
            >
              {actionLoading === 'schedule' ? <RefreshCw size={16} className="animate-spin" /> : <CalendarClock size={16} />}
              {t('scheduled')}
            </button>
          )}
          
          <div className="w-full grid grid-cols-2 gap-2 mt-2">
            <button 
              onClick={() => handleAction('creative', `/api/content/${item.id}/creative`)}
              disabled={actionLoading !== null}
              className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors flex justify-center items-center gap-1"
            >
              <ImageIcon size={14} /> {t('regenerate')}
            </button>
            <button 
              onClick={() => handleAction('review', `/api/content/${item.id}/review`)}
              disabled={actionLoading !== null}
              className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors flex justify-center items-center gap-1"
            >
              <CheckSquare size={14} /> {t('regenerate')}
            </button>
            <button 
              onClick={() => handleAction('regenerate', `/api/content/${item.id}/regenerate`)}
              disabled={actionLoading !== null}
              className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors flex justify-center items-center gap-1"
            >
              <RefreshCw size={14} className={actionLoading === 'regenerate' ? 'animate-spin' : ''} /> {t('regenerate')}
            </button>
            <button 
              onClick={() => handleAction('translate', `/api/content/${item.id}/translate`, 'post', {target_lang: item.language === 'he' ? 'en' : 'he'})}
              disabled={actionLoading !== null}
              className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors flex justify-center items-center gap-1"
            >
              <Globe size={14} /> {t('translate')}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
