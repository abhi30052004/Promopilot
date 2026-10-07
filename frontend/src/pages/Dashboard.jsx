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
    <div className="flex flex-col gap-8 max-w-7xl mx-auto pb-10">
      {toast && (
        <div className={`fixed bottom-4 end-4 px-6 py-3 rounded-lg shadow-lg text-white ${toast.type === 'error' ? 'bg-red-500' : 'bg-emerald-500'} z-50 transition-all`}>
          {toast.msg}
        </div>
      )}

      <div className="flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border border-slate-100">
        <div>
          <h2 className="text-xl font-bold text-slate-800">לוח בקרה</h2>
          <p className="text-slate-500 text-sm">סיכום סטטוס תוכן ונכסים</p>
        </div>
        <span className={`px-4 py-2 rounded-full text-sm font-bold ${stats?.approval_mode === 'AUTOMATION' ? 'bg-emerald-100 text-emerald-700' : 'bg-indigo-100 text-indigo-700'}`}>
          {stats?.approval_mode === 'AUTOMATION' ? 'Automation' : 'Human Approval'}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatCard 
          title="סך הכל נכסים (Scraped)" 
          value={stats?.scraped_properties || 0} 
          icon={FileText} 
          colorClass="bg-blue-100 text-blue-600" 
        />
        <StatCard 
          title="נכסים ממתינים" 
          value={stats?.pending_properties || 0} 
          icon={Clock} 
          colorClass="bg-amber-100 text-amber-600" 
        />
        <StatCard 
          title="נכסים שאושרו/נדחו" 
          value={`${stats?.approved_properties || 0} / ${stats?.rejected_properties || 0}`} 
          icon={CheckCircle} 
          colorClass="bg-emerald-100 text-emerald-600" 
        />
        
        <StatCard 
          title="תוכן ממתין לאישור" 
          value={stats?.content_pending_review || 0} 
          icon={Clock} 
          colorClass="bg-amber-100 text-amber-600" 
        />
        <StatCard 
          title="תוכן מאושר" 
          value={stats?.approved_content || 0} 
          icon={CheckCircle} 
          colorClass="bg-emerald-100 text-emerald-600" 
        />
        <StatCard 
          title="תוכן מתוזמן" 
          value={stats?.scheduled || 0} 
          icon={CalendarClock} 
          colorClass="bg-indigo-100 text-indigo-600" 
        />
        <StatCard 
          title="תוכן שפורסם" 
          value={stats?.published || 0} 
          icon={UploadCloud} 
          colorClass="bg-teal-100 text-teal-600" 
        />
        <StatCard 
          title="תוכן שנדחה" 
          value={stats?.rejected_content || 0} 
          icon={AlertTriangle} 
          colorClass="bg-rose-100 text-rose-600" 
        />
      </div>
    </div>
  );
}
