import React, { useState, useEffect } from 'react';
import { 
  ChevronRight, ChevronLeft, Calendar as CalendarIcon, 
  Image as ImageIcon, Video, MessageCircle, Camera, Send 
} from 'lucide-react';
import { startOfWeek, addWeeks, subWeeks, addDays, format, isSameDay, isToday } from 'date-fns';
import api from '../lib/api';
import ContentDrawer from '../components/ContentDrawer';

const STATUS_COLORS = {
  draft: 'bg-slate-300',
  pending_approval: 'bg-amber-400',
  approved: 'bg-blue-400',
  scheduled: 'bg-purple-500',
  published: 'bg-emerald-500',
  failed: 'bg-red-500',
  rejected: 'bg-rose-600'
};

const STATUS_LABELS = {
  draft: 'טיוטה',
  pending_approval: 'ממתין לאישור',
  approved: 'מאושר',
  scheduled: 'מתוזמן',
  published: 'פורסם',
  failed: 'נכשל',
  rejected: 'נדחה'
};

const PLATFORM_ICONS = {
  facebook: <MessageCircle size={14} />,
  instagram: <Camera size={14} />,
  tiktok: <Video size={14} />,
  x: <Send size={14} />,
  telegram: <MessageCircle size={14} />
};

const serverDate = (value) => new Date(value && !value.endsWith('Z') ? `${value}Z` : value);

export default function Calendar() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [items, setItems] = useState([]);
  const [properties, setProperties] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [selectedItem, setSelectedItem] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  useEffect(() => {
    fetchData();
  }, [currentDate]);

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const visibleStart = startOfWeek(currentDate, { weekStartsOn: 0 });
      const visibleEnd = addDays(visibleStart, 6);
      const [propsRes, contentRes] = await Promise.all([
        api.get('/api/properties'),
        api.get('/api/calendar', {
          params: {
            start: format(visibleStart, 'yyyy-MM-dd'),
            end: format(visibleEnd, 'yyyy-MM-dd'),
          },
        })
      ]);
      
      const propMap = {};
      propsRes.data.forEach(p => propMap[p.id] = p.name);
      setProperties(propMap);
      setItems(contentRes.data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Could not load the publishing calendar.');
    } finally {
      setLoading(false);
    }
  };

  const handlePrevWeek = () => setCurrentDate(subWeeks(currentDate, 1));
  const handleNextWeek = () => setCurrentDate(addWeeks(currentDate, 1));
  const handleToday = () => setCurrentDate(new Date());

  const weekStart = startOfWeek(currentDate, { weekStartsOn: 0 }); // Sunday
  const days = Array.from({ length: 7 }).map((_, i) => addDays(weekStart, i));

  const getItemsForDay = (date) => {
    return items
      .filter(item => ['SCHEDULED', 'PUBLISHED'].includes(item.publish_status) && item.scheduled_at && isSameDay(serverDate(item.scheduled_at), date))
      .sort((a, b) => serverDate(a.scheduled_at) - serverDate(b.scheduled_at));
  };

  return (
    <div className="flex flex-col gap-6 h-full">
      {/* Header */}
      <div className="flex justify-between items-center bg-white p-4 rounded-xl shadow-sm border border-slate-100">
        <div className="flex items-center gap-4">
          <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
            <CalendarIcon size={24} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-800">
              {format(weekStart, 'MMMM yyyy')}
            </h2>
            <p className="text-sm text-slate-500">תצוגה שבועית</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button 
            onClick={handleToday}
            className="px-4 py-2 border border-slate-200 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
          >
            היום
          </button>
          <div className="flex items-center bg-slate-100 rounded-lg p-1">
            <button onClick={handleNextWeek} className="p-1.5 rounded hover:bg-white hover:shadow-sm transition-all" title="שבוע הבא">
              <ChevronRight size={18} />
            </button>
            <button onClick={handlePrevWeek} className="p-1.5 rounded hover:bg-white hover:shadow-sm transition-all" title="שבוע קודם">
              <ChevronLeft size={18} />
            </button>
          </div>
        </div>
      </div>

      {error && <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}

      {/* Legend */}
      <div className="flex flex-wrap gap-4 bg-white p-3 rounded-xl shadow-sm border border-slate-100 text-xs text-slate-600">
        {Object.entries(STATUS_LABELS).map(([key, label]) => (
          <div key={key} className="flex items-center gap-1.5">
            <div className={`w-3 h-3 rounded-full ${STATUS_COLORS[key]}`} />
            <span>{label}</span>
          </div>
        ))}
      </div>

      {/* Grid */}
      <div className="flex-1 grid grid-cols-7 gap-4 min-h-[500px]">
        {days.map((day, i) => {
          const isWeekend = day.getDay() === 5 || day.getDay() === 6; // Friday = 5, Saturday = 6
          const isCurrentDay = isToday(day);
          const dayItems = getItemsForDay(day);
          
          return (
            <div 
              key={day.toISOString()} 
              className={`flex flex-col rounded-xl overflow-hidden border ${isCurrentDay ? 'border-indigo-300 shadow-md ring-1 ring-indigo-300' : 'border-slate-200 shadow-sm'} ${isWeekend ? 'bg-slate-50/70' : 'bg-white'}`}
            >
              <div className={`p-3 text-center border-b ${isCurrentDay ? 'bg-indigo-50 border-indigo-200' : 'border-slate-100'}`}>
                <div className={`text-xs font-semibold mb-1 ${isWeekend ? 'text-slate-400' : 'text-slate-500'}`}>
                  {['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת'][i]}
                </div>
                <div className={`text-xl font-bold ${isCurrentDay ? 'text-indigo-600' : 'text-slate-800'}`}>
                  {format(day, 'dd')}
                </div>
              </div>
              
              <div className="flex-1 p-2 flex flex-col gap-2 overflow-y-auto min-h-[150px]">
                {loading ? (
                  <div className="animate-pulse flex flex-col gap-2">
                    <div className="h-10 bg-slate-200 rounded"></div>
                    <div className="h-10 bg-slate-200 rounded"></div>
                  </div>
                ) : dayItems.length > 0 ? (
                  dayItems.map(item => (
                    <div 
                      key={item.id}
                      onClick={() => { setSelectedItem(item); setIsDrawerOpen(true); }}
                      className="group p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm cursor-pointer transition-all flex flex-col gap-1.5 relative overflow-hidden"
                    >
                      {/* Status indicator bar */}
                      <div className={`absolute start-0 top-0 bottom-0 w-1 ${STATUS_COLORS[item.status]}`} />
                      
                      <div className="flex justify-between items-center ps-2">
                        <span className="text-xs font-bold text-slate-700 dir-ltr text-start">
                          {format(serverDate(item.scheduled_at), 'HH:mm')}
                        </span>
                        <div className="flex items-center gap-1.5 text-slate-400">
                          <span title={item.platform}>{PLATFORM_ICONS[item.platform]}</span>
                          <span title={item.kind === 'story' ? 'סטורי' : 'פוסט'}>
                            {item.kind === 'story' ? <Video size={14} /> : <ImageIcon size={14} />}
                          </span>
                        </div>
                      </div>
                      
                      <div className="ps-2 text-xs font-medium text-slate-800 truncate" title={properties[item.property_id]}>
                        {properties[item.property_id] || 'נכס'}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="flex-1 flex items-center justify-center text-slate-300 text-xs">
                    אין תוכן
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {isDrawerOpen && selectedItem && (
        <ContentDrawer 
          item={selectedItem}
          properties={properties}
          onClose={() => setIsDrawerOpen(false)}
          onUpdate={fetchData}
        />
      )}
    </div>
  );
}
