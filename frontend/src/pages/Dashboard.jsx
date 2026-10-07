import React, { useState, useEffect } from 'react';
import { 
  FileText, PlaySquare, CalendarClock, CheckCircle, 
  Clock, AlertTriangle, RefreshCw, Zap, UploadCloud 
} from 'lucide-react';
import api from '../lib/api';
import { useLanguage } from '../lib/LanguageContext';

const StatCard = ({ title, value, icon: Icon, colorClass }) => (
  <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 flex items-center gap-4">
    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${colorClass}`}>
      <Icon size={24} />
    </div>
    <div>
      <p className="text-sm text-slate-500 font-medium">{title}</p>
      <h3 className="text-2xl font-bold text-slate-800">{value}</h3>
    </div>
  </div>
);

export default function Dashboard() {
  const { t } = useLanguage();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [toast, setToast] = useState(null);

  const fetchStats = async () => {
    try {
      const res = await api.get('/api/dashboard/stats');
      setStats(res.data);
    } catch (err) {
      showToast('שגיאה בטעינת נתונים', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleAction = async (action, endpoint, payload = {}) => {
    setActionLoading(action);
    try {
      if (action === 'generate') {
        await api.post(endpoint, payload);
      } else {
        await api.post(endpoint, payload);
      }
      showToast('הפעולה נשלחה לביצוע');
      setTimeout(fetchStats, 1000);
    } catch (err) {
      showToast('שגיאה בביצוע הפעולה', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="animate-spin text-indigo-600"><RefreshCw size={32} /></div>
      </div>
    );
  }

  const todayStr = new Date().toISOString().split('T')[0];

  return (
    <div className="flex flex-col gap-8 max-w-7xl mx-auto">
      {toast && (
        <div className={`fixed bottom-4 end-4 px-6 py-3 rounded-lg shadow-lg text-white ${toast.type === 'error' ? 'bg-red-500' : 'bg-emerald-500'} z-50 transition-all`}>
          {toast.msg}
        </div>
      )}

      <div className="flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border border-slate-100">
        <div>
          <h2 className="text-xl font-bold text-slate-800">{t('daily_summary')}</h2>
          <p className="text-slate-500 text-sm">{t('content_status')}</p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => handleAction('sync', '/api/properties/sync')}
            disabled={actionLoading !== null}
            className="flex items-center gap-2 px-4 py-2 bg-slate-100 text-slate-700 hover:bg-slate-200 rounded-lg font-medium transition-colors disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw size={18} className={actionLoading === 'sync' ? 'animate-spin' : ''} />
            {t('website_sync')}
          </button>
          
          <button 
            onClick={() => handleAction('generate', '/api/agent/run', { date: todayStr, mode: 'manual' })}
            disabled={actionLoading !== null}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white hover:bg-indigo-700 rounded-lg font-medium transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
          >
            {actionLoading === 'generate' ? <RefreshCw size={18} className="animate-spin" /> : <Zap size={18} />}
            {t('create_plan')}
          </button>
          
          <button 
            onClick={() => handleAction('publish', '/api/scheduler/run-daily')}
            disabled={actionLoading !== null}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white hover:bg-emerald-600 rounded-lg font-medium transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
          >
            <UploadCloud size={18} />
            {t('publish_now')}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatCard 
          title={t('posts_today')} 
          value={stats?.posts_today || 0} 
          icon={FileText} 
          colorClass="bg-blue-100 text-blue-600" 
        />
        <StatCard 
          title={t('stories_today')} 
          value={stats?.stories_today || 0} 
          icon={PlaySquare} 
          colorClass="bg-purple-100 text-purple-600" 
        />
        <StatCard 
          title={t('scheduled')} 
          value={stats?.scheduled || 0} 
          icon={CalendarClock} 
          colorClass="bg-emerald-100 text-emerald-600" 
        />
        <StatCard 
          title={t('published')} 
          value={stats?.published || 0} 
          icon={CheckCircle} 
          colorClass="bg-teal-100 text-teal-600" 
        />
        <StatCard 
          title={t('awaiting_approval')} 
          value={stats?.pending_approval || 0} 
          icon={Clock} 
          colorClass="bg-amber-100 text-amber-600" 
        />
        <StatCard 
          title={t('failed')} 
          value={stats?.failed || 0} 
          icon={AlertTriangle} 
          colorClass="bg-red-100 text-red-600" 
        />
      </div>
    </div>
  );
}
