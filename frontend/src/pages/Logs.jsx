import React, { useState, useEffect } from 'react';
import { 
  Terminal, Play, Pause, ChevronDown, ChevronUp, AlertCircle, 
  CheckCircle2, Clock, RotateCw, Filter, RefreshCw
} from 'lucide-react';
import api from '../lib/api';
import { format } from 'date-fns';

export default function Logs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [expandedRows, setExpandedRows] = useState({});
  const [filters, setFilters] = useState({ source: '', status: '' });
  
  const fetchLogs = async () => {
    try {
      const res = await api.get('/api/logs');
      setLogs(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [isPaused]);

  const toggleRow = (id) => {
    setExpandedRows(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const getStatusBadge = (status) => {
    const s = status?.toUpperCase() || 'UNKNOWN';
    if (s === 'SUCCESS' || s === 'PUBLISHED') return <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 text-emerald-700 flex items-center gap-1 w-max"><CheckCircle2 size={12}/> {s}</span>;
    if (s === 'FAILED') return <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-100 text-red-700 flex items-center gap-1 w-max"><AlertCircle size={12}/> {s}</span>;
    if (s === 'RETRY' || s === 'PENDING') return <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-700 flex items-center gap-1 w-max"><RotateCw size={12}/> {s}</span>;
    return <span className="px-2 py-0.5 rounded text-xs font-bold bg-slate-100 text-slate-700 w-max">{s}</span>;
  };

  const filteredLogs = logs.filter(l => {
    if (filters.source) {
      const source = l.type === 'agent' ? l.agent : l.type === 'automation' ? l.action : `publisher (${l.platform})`;
      if (!source.toLowerCase().includes(filters.source.toLowerCase())) return false;
    }
    if (filters.status && l.status?.toLowerCase() !== filters.status.toLowerCase()) return false;
    return true;
  });

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto h-full min-h-[calc(100vh-theme(spacing.20))]">
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100 flex flex-wrap justify-between items-center gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
            <Terminal size={20} className="text-slate-500" />
            יומן מערכת (Logs)
          </h2>
          <p className="text-sm text-slate-500 mt-1">צפה ביומן הפעולות של סוכני ה-AI והמפרסמים בזמן אמת</p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5">
            <Filter size={16} className="text-slate-400" />
            <input 
              type="text" 
              placeholder="סינון מקור..." 
              value={filters.source}
              onChange={e => setFilters({...filters, source: e.target.value})}
              className="bg-transparent border-none outline-none text-sm w-32"
            />
            <select 
              value={filters.status}
              onChange={e => setFilters({...filters, status: e.target.value})}
              className="bg-transparent border-s border-slate-200 ps-2 ms-1 outline-none text-sm text-slate-600"
            >
              <option value="">כל הסטטוסים</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="retry">Retry</option>
              <option value="published">Published</option>
            </select>
          </div>
          
          <button 
            onClick={() => setIsPaused(!isPaused)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border ${isPaused ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-indigo-50 text-indigo-700 border-indigo-200'}`}
          >
            {isPaused ? <Play size={16} /> : <Pause size={16} />}
            {isPaused ? 'המשך עדכון' : 'השהה עדכון'}
          </button>
        </div>
      </div>

      <div className="flex-1 bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden flex flex-col">
        {loading && logs.length === 0 ? (
          <div className="flex-1 flex justify-center items-center">
            <RefreshCw className="animate-spin text-slate-400" />
          </div>
        ) : (
          <div className="overflow-auto flex-1">
            <table className="w-full text-start border-collapse">
              <thead className="sticky top-0 bg-slate-50 border-b border-slate-200 text-slate-500 text-xs shadow-sm z-10">
                <tr>
                  <th className="py-3 px-4 font-medium text-start w-48">זמן</th>
                  <th className="py-3 px-4 font-medium text-start">מקור (Source)</th>
                  <th className="py-3 px-4 font-medium text-start">סטטוס</th>
                  <th className="py-3 px-4 font-medium text-start">מידע נוסף</th>
                  <th className="py-3 px-4 font-medium text-end w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm font-mono">
                {filteredLogs.map(log => {
                  const isAgent = log.type === 'agent';
                  const isAutomation = log.type === 'automation';
                  const sourceStr = isAgent ? log.agent : isAutomation ? log.action : `Publisher (${log.platform})`;
                  const hasDetails = log.message || log.error || log.response;
                  const isExpanded = expandedRows[log.id];
                  
                  return (
                    <React.Fragment key={log.id}>
                      <tr 
                        className={`hover:bg-slate-50 transition-colors ${hasDetails ? 'cursor-pointer' : ''} ${log.status?.toLowerCase() === 'failed' ? 'bg-red-50/30' : ''}`}
                        onClick={() => hasDetails && toggleRow(log.id)}
                      >
                        <td className="py-3 px-4 text-slate-500 whitespace-nowrap">
                          {format(new Date(log.created_at), 'yyyy-MM-dd HH:mm:ss')}
                        </td>
                        <td className="py-3 px-4 font-semibold text-slate-700">
                          {sourceStr}
                        </td>
                        <td className="py-3 px-4">
                          {getStatusBadge(log.status)}
                        </td>
                        <td className="py-3 px-4 text-slate-500 text-xs flex gap-4">
                          {isAgent ? (
                            <>
                              {log.provider && <span><span className="text-slate-400">LLM:</span> {log.provider}</span>}
                              {log.duration_ms && <span className="flex items-center gap-1"><Clock size={12}/> {log.duration_ms}ms</span>}
                              {log.retry_count > 0 && <span className="text-amber-600">Retry: {log.retry_count}</span>}
                            </>
                          ) : isAutomation ? (
                            <>
                              <span>{log.entity_type} #{log.entity_id}</span>
                              <span>Mode: {log.mode}</span>
                            </>
                          ) : (
                            <>
                              {log.content_item_id && <span><span className="text-slate-400">Item ID:</span> {log.content_item_id}</span>}
                              {log.attempt > 1 && <span className="text-amber-600">Attempt: {log.attempt}</span>}
                            </>
                          )}
                        </td>
                        <td className="py-3 px-4 text-end text-slate-400">
                          {hasDetails && (isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />)}
                        </td>
                      </tr>
                      {isExpanded && hasDetails && (
                        <tr className="bg-slate-50/80 border-b border-slate-200">
                          <td colSpan={5} className="p-4 pt-0">
                            <div className="bg-slate-900 rounded-lg p-4 text-slate-300 text-xs overflow-x-auto whitespace-pre-wrap border border-slate-800 shadow-inner mt-2">
                              {log.error ? (
                                <span className="text-red-400">{log.error}</span>
                              ) : log.message ? (
                                log.message
                              ) : (
                                JSON.stringify(log.response, null, 2)
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
            {filteredLogs.length === 0 && (
              <div className="text-center text-slate-400 py-12">לא נמצאו רשומות לוג מתאימות</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
