import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageCircle, Video, Play, Heart, Camera, Send,
  MessageSquare, Share2, Bookmark, Repeat2, ExternalLink, ShieldAlert,
  MoreHorizontal, ThumbsUp
} from 'lucide-react';
import api from '../lib/api';
import { formatDistanceToNow } from 'date-fns';
import { he } from 'date-fns/locale';

const PLATFORMS = ['facebook', 'instagram', 'tiktok', 'x', 'telegram', 'stories'];

export default function Feeds() {
  const [activeTab, setActiveTab] = useState('instagram');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [prevIds, setPrevIds] = useState(new Set());
  
  const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  const fetchFeed = async () => {
    try {
      let res;
      if (activeTab === 'stories') {
        res = await api.get('/api/content', { params: { status: 'published', kind: 'story' } });
      } else {
        res = await api.get(`/api/feeds/${activeTab}`);
      }
      
      const newItems = res.data;
      const currentIds = new Set(newItems.map(i => i.id));
      
      // If not initial load, detect new items
      if (!loading && items.length > 0) {
        setPrevIds(new Set(items.map(i => i.id)));
      }
      
      setItems(newItems);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchFeed();
  }, [activeTab]);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchFeed();
    }, 10000); // 10 seconds refresh
    return () => clearInterval(interval);
  }, [activeTab, items]);

  const BrandAvatar = () => (
    <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-sm overflow-hidden shrink-0">
      <img src="https://ui-avatars.com/api/?name=%D7%A6%D7%9C%D7%A2+%D7%94%D7%94%D7%A8&background=4f46e5&color=fff" alt="Avatar" className="w-full h-full object-cover" />
    </div>
  );

  const DemoBadge = ({ externalId }) => {
    const isLive = externalId && !externalId.includes('demo-');
    return (
      <div className={`flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded ${isLive ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
        <ShieldAlert size={10} />
        {isLive ? 'LIVE' : 'DEMO PUBLISHER'}
      </div>
    );
  };

  // Mock fake engagement generator based on ID for consistency
  const getFakeStats = (id) => {
    const num = (id * 13) % 100;
    return {
      likes: num > 0 ? (num * 15).toLocaleString() : '1,234',
      comments: num > 0 ? (num * 3) : '89',
      shares: num > 0 ? num : '12',
      views: num > 0 ? (num * 105).toLocaleString() : '14.5K'
    };
  };

  const FacebookCard = ({ item }) => {
    const stats = getFakeStats(item.id);
    const isNew = !loading && prevIds.size > 0 && !prevIds.has(item.id);
    
    return (
      <div className={`bg-white rounded-xl shadow-md overflow-hidden max-w-xl mx-auto transition-all ${isNew ? 'ring-2 ring-indigo-500 shadow-indigo-100 animate-pulse' : ''}`}>
        <div className="p-4 flex items-start justify-between">
          <div className="flex gap-3">
            <BrandAvatar />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900">צלע ההר - כפר נופש יוקרתי</span>
                <DemoBadge externalId={item.external_id} />
              </div>
              <div className="text-xs text-slate-500 flex items-center gap-1">
                {formatDistanceToNow(new Date(item.scheduled_at || item.created_at), { addSuffix: true, locale: he })} · 
                <Globe size={10} />
              </div>
            </div>
          </div>
          <MoreHorizontal className="text-slate-500" size={20} />
        </div>
        
        <div className="px-4 pb-3 text-[15px] text-slate-800 whitespace-pre-wrap leading-snug">
          {item.caption}
          {item.hashtags && <div className="text-blue-600 mt-2">{item.hashtags}</div>}
          {item.link && <div className="text-blue-600 font-medium hover:underline cursor-pointer">{item.link}</div>}
        </div>
        
        {item.image_path && (
          <img src={`${BASE_URL}/media/${item.image_path.replace(/^\/+/, '')}`} alt="Post" className="w-full object-cover max-h-[500px]" />
        )}
        
        <div className="p-3">
          <div className="flex justify-between items-center text-slate-500 text-xs border-b border-slate-200 pb-3 mb-1">
            <div className="flex items-center gap-1">
              <div className="bg-blue-500 text-white p-0.5 rounded-full"><ThumbsUp size={12} fill="white" /></div>
              {stats.likes}
            </div>
            <div>{stats.comments} תגובות · {stats.shares} שיתופים</div>
          </div>
          <div className="flex justify-between pt-1">
            <button className="flex-1 flex items-center justify-center gap-2 text-slate-600 font-medium text-sm py-1.5 hover:bg-slate-50 rounded">
              <ThumbsUp size={20} /> אהבתי
            </button>
            <button className="flex-1 flex items-center justify-center gap-2 text-slate-600 font-medium text-sm py-1.5 hover:bg-slate-50 rounded">
              <MessageSquare size={20} /> תגובה
            </button>
            <button className="flex-1 flex items-center justify-center gap-2 text-slate-600 font-medium text-sm py-1.5 hover:bg-slate-50 rounded">
              <Share2 size={20} /> שיתוף
            </button>
          </div>
        </div>
      </div>
    );
  };

  const InstagramCard = ({ item }) => {
    const stats = getFakeStats(item.id);
    const isNew = !loading && prevIds.size > 0 && !prevIds.has(item.id);
    
    return (
      <div className={`bg-white rounded border border-slate-200 max-w-[470px] mx-auto overflow-hidden transition-all ${isNew ? 'ring-2 ring-pink-500 shadow-pink-100' : ''}`}>
        <div className="flex items-center justify-between p-3 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <BrandAvatar />
            <div className="flex flex-col">
              <span className="font-semibold text-sm text-slate-900 flex items-center gap-2">
                tzel_hahar <DemoBadge externalId={item.external_id} />
              </span>
            </div>
          </div>
          <MoreHorizontal size={20} className="text-slate-800" />
        </div>
        
        {item.image_path && (
          <img src={`${BASE_URL}/media/${item.image_path.replace(/^\/+/, '')}`} alt="Post" className="w-full aspect-[4/5] object-cover" />
        )}
        
        <div className="p-4 pt-3">
          <div className="flex justify-between items-center mb-3">
            <div className="flex gap-4">
              <Heart size={24} className="text-slate-800 hover:text-slate-500 cursor-pointer" />
              <MessageCircle size={24} className="text-slate-800 hover:text-slate-500 cursor-pointer" style={{transform: 'scaleX(-1)'}} />
              <Share2 size={24} className="text-slate-800 hover:text-slate-500 cursor-pointer" />
            </div>
            <Bookmark size={24} className="text-slate-800 hover:text-slate-500 cursor-pointer" />
          </div>
          <div className="font-semibold text-sm text-slate-900 mb-1">{stats.likes} לייקים</div>
          <div className="text-sm text-slate-900 whitespace-pre-wrap leading-relaxed">
            <span className="font-semibold me-2">tzel_hahar</span>
            {item.caption}
          </div>
          {item.hashtags && <div className="text-sm text-blue-900 mt-1">{item.hashtags}</div>}
          <div className="text-[10px] text-slate-500 uppercase tracking-wide mt-2">
            {formatDistanceToNow(new Date(item.scheduled_at || item.created_at), { addSuffix: true, locale: he })}
          </div>
        </div>
      </div>
    );
  };

  const TikTokCard = ({ item }) => {
    const stats = getFakeStats(item.id);
    const isNew = !loading && prevIds.size > 0 && !prevIds.has(item.id);
    
    return (
      <div className={`bg-black rounded-xl max-w-[400px] h-[700px] mx-auto relative overflow-hidden text-white transition-all ${isNew ? 'ring-2 ring-cyan-500 shadow-cyan-900/50' : ''}`}>
        {item.image_path ? (
          <img src={`${BASE_URL}/media/${item.image_path.replace(/^\/+/, '')}`} alt="Video Thumbnail" className="w-full h-full object-cover opacity-80" />
        ) : (
          <div className="w-full h-full bg-slate-900 flex items-center justify-center">No media</div>
        )}
        
        <div className="absolute top-4 start-4">
          <DemoBadge externalId={item.external_id} />
        </div>
        
        <div className="absolute bottom-4 start-4 end-16 flex flex-col gap-2 z-10">
          <div className="font-bold text-[17px]">@tzel_hahar</div>
          <div className="text-sm line-clamp-3 text-white/90">
            {item.caption}
          </div>
          {item.hashtags && <div className="text-sm font-semibold text-white">{item.hashtags}</div>}
        </div>
        
        <div className="absolute bottom-4 end-4 flex flex-col gap-4 items-center z-10">
          <div className="w-12 h-12 rounded-full bg-white p-0.5 relative mb-2">
            <BrandAvatar />
            <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 bg-rose-500 rounded-full w-4 h-4 flex items-center justify-center text-[10px]">+</div>
          </div>
          <div className="flex flex-col items-center gap-1">
            <div className="bg-slate-800/60 p-3 rounded-full"><Heart size={24} fill="white" /></div>
            <span className="text-xs font-semibold">{stats.likes}</span>
          </div>
          <div className="flex flex-col items-center gap-1">
            <div className="bg-slate-800/60 p-3 rounded-full"><MessageCircle size={24} fill="white" /></div>
            <span className="text-xs font-semibold">{stats.comments}</span>
          </div>
          <div className="flex flex-col items-center gap-1">
            <div className="bg-slate-800/60 p-3 rounded-full"><Bookmark size={24} fill="white" /></div>
            <span className="text-xs font-semibold">{stats.shares}</span>
          </div>
          <div className="flex flex-col items-center gap-1">
            <div className="bg-slate-800/60 p-3 rounded-full"><Share2 size={24} fill="white" style={{transform: 'scaleX(-1)'}}/></div>
            <span className="text-xs font-semibold">Share</span>
          </div>
        </div>
      </div>
    );
  };

  const XCard = ({ item }) => {
    const stats = getFakeStats(item.id);
    const isNew = !loading && prevIds.size > 0 && !prevIds.has(item.id);
    
    return (
      <div className={`bg-white border-b border-slate-200 max-w-xl mx-auto p-4 flex gap-3 transition-all ${isNew ? 'bg-indigo-50/30' : ''}`}>
        <BrandAvatar />
        <div className="flex-1">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-[15px] text-slate-900">צלע ההר</span>
            <span className="text-[15px] text-slate-500">@tzel_hahar</span>
            <span className="text-[15px] text-slate-500">·</span>
            <span className="text-[15px] text-slate-500 hover:underline cursor-pointer">
              {formatDistanceToNow(new Date(item.scheduled_at || item.created_at), { locale: he }).replace('בערך ', '').replace(' לפני', '')}
            </span>
            <div className="ms-auto"><DemoBadge externalId={item.external_id} /></div>
          </div>
          
          <div className="text-[15px] text-slate-900 mt-1 whitespace-pre-wrap leading-snug">
            {item.caption}
            {item.hashtags && <div className="text-[#1d9bf0] mt-1">{item.hashtags}</div>}
            {item.link && <div className="text-[#1d9bf0] hover:underline cursor-pointer">{item.link}</div>}
          </div>
          
          {item.image_path && (
            <div className="mt-3 rounded-2xl border border-slate-200 overflow-hidden">
              <img src={`${BASE_URL}/media/${item.image_path.replace(/^\/+/, '')}`} alt="Post" className="w-full object-cover max-h-[500px]" />
            </div>
          )}
          
          <div className="flex justify-between text-slate-500 mt-3 max-w-md">
            <div className="flex items-center gap-2 hover:text-[#1d9bf0] cursor-pointer group">
              <div className="p-2 rounded-full group-hover:bg-[#1d9bf0]/10 transition-colors"><MessageCircle size={18} /></div>
              <span className="text-xs">{stats.comments}</span>
            </div>
            <div className="flex items-center gap-2 hover:text-[#00ba7c] cursor-pointer group">
              <div className="p-2 rounded-full group-hover:bg-[#00ba7c]/10 transition-colors"><Repeat2 size={18} /></div>
              <span className="text-xs">{stats.shares}</span>
            </div>
            <div className="flex items-center gap-2 hover:text-[#f91880] cursor-pointer group">
              <div className="p-2 rounded-full group-hover:bg-[#f91880]/10 transition-colors"><Heart size={18} /></div>
              <span className="text-xs">{stats.likes}</span>
            </div>
            <div className="flex items-center gap-2 hover:text-[#1d9bf0] cursor-pointer group">
              <div className="p-2 rounded-full group-hover:bg-[#1d9bf0]/10 transition-colors"><Share2 size={18} /></div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const TelegramCard = ({ item }) => {
    const isNew = !loading && prevIds.size > 0 && !prevIds.has(item.id);
    
    return (
      <div className="max-w-xl mx-auto w-full px-4 mb-4 flex flex-col">
        <div className="self-center bg-slate-200/50 text-slate-500 text-xs font-medium px-3 py-1 rounded-full mb-4">
          היום
        </div>
        <div className="flex gap-2">
          <BrandAvatar />
          <div className="flex flex-col items-start max-w-[85%]">
            <div className={`bg-white rounded-2xl rounded-tr-none shadow-sm border border-slate-200 p-2 overflow-hidden transition-all relative ${isNew ? 'ring-2 ring-sky-400' : ''}`}>
              <div className="absolute top-2 start-2 z-10">
                <DemoBadge externalId={item.external_id} />
              </div>
              {item.image_path && (
                <img src={`${BASE_URL}/media/${item.image_path.replace(/^\/+/, '')}`} alt="Post" className="w-full rounded-xl mb-2 object-cover" />
              )}
              <div className="px-2 pt-1 pb-2">
                <div className="font-semibold text-sky-500 text-sm mb-1">צלע ההר | וילות וצימרים</div>
                <div className="text-[15px] text-slate-900 whitespace-pre-wrap leading-snug">
                  {item.caption}
                  {item.hashtags && <div className="text-sky-600 mt-2">{item.hashtags}</div>}
                  {item.link && <div className="text-sky-600 hover:underline cursor-pointer mt-1">{item.link}</div>}
                </div>
                <div className="text-end text-[11px] text-slate-400 mt-1 flex justify-end gap-1 items-center">
                  {formatDistanceToNow(new Date(item.scheduled_at || item.created_at), { locale: he }).replace('בערך ', '')}
                  <span className="text-sky-500">✓✓</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const StoryViewer = ({ items }) => {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [progress, setProgress] = useState(0);
    
    useEffect(() => {
      if (items.length === 0) return;
      setProgress(0);
      
      const interval = setInterval(() => {
        setProgress(p => {
          if (p >= 100) {
            setCurrentIndex((curr) => (curr + 1) % items.length);
            return 0;
          }
          return p + 2; // increments every 100ms -> 50 steps -> 5000ms
        });
      }, 100);
      
      return () => clearInterval(interval);
    }, [currentIndex, items]);

    if (items.length === 0) {
      return <div className="text-center text-slate-500 py-20 bg-white rounded-xl max-w-sm mx-auto shadow-sm">אין סטוריז זמינים להצגה</div>;
    }

    const currentItem = items[currentIndex];

    return (
      <div className="relative bg-black rounded-xl max-w-sm aspect-[9/16] mx-auto overflow-hidden shadow-2xl flex flex-col text-white group">
        <div className="absolute top-0 inset-x-0 h-24 bg-gradient-to-b from-black/70 to-transparent z-10" />
        
        {/* Progress Bars */}
        <div className="absolute top-3 inset-x-3 flex gap-1.5 z-20">
          {items.map((_, i) => (
            <div key={i} className="h-1 bg-white/30 rounded-full flex-1 overflow-hidden">
              <div 
                className="h-full bg-white transition-all duration-100 linear" 
                style={{ width: i < currentIndex ? '100%' : i === currentIndex ? `${progress}%` : '0%' }} 
              />
            </div>
          ))}
        </div>
        
        {/* Header */}
        <div className="absolute top-7 start-3 end-3 flex justify-between items-center z-20">
          <div className="flex items-center gap-2">
            <BrandAvatar />
            <span className="font-semibold text-sm drop-shadow-md">צלע ההר</span>
            <span className="text-white/70 text-xs drop-shadow-md">
              {formatDistanceToNow(new Date(currentItem.scheduled_at || currentItem.created_at), { locale: he }).replace('בערך ', '')}
            </span>
          </div>
          <MoreHorizontal size={20} className="drop-shadow-md" />
        </div>

        {/* Media */}
        <div className="flex-1 bg-zinc-900 flex items-center justify-center relative">
          {currentItem.image_path ? (
            <img src={`${BASE_URL}/media/${currentItem.image_path.replace(/^\/+/, '')}`} className="w-full h-full object-cover" alt="Story" />
          ) : (
            <div className="text-white/50">No media found</div>
          )}
          
          <div className="absolute inset-0 flex">
            <div className="flex-1" onClick={() => { setCurrentIndex(i => i > 0 ? i - 1 : items.length - 1); setProgress(0); }} />
            <div className="flex-1" onClick={() => { setCurrentIndex(i => (i + 1) % items.length); setProgress(0); }} />
          </div>
        </div>

        {/* Text Area (Fallback if not burned in image) */}
        {(currentItem.caption || currentItem.cta) && (
          <div className="absolute bottom-16 inset-x-4 text-center z-20">
            <div className="bg-black/40 backdrop-blur-md text-white p-3 rounded-xl text-sm leading-snug drop-shadow-lg">
              {currentItem.caption}
              <div className="font-bold mt-1 text-sky-300">{currentItem.cta}</div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="absolute bottom-0 inset-x-0 h-32 bg-gradient-to-t from-black/80 to-transparent z-10 pointer-events-none" />
        <div className="absolute bottom-4 inset-x-4 flex gap-3 z-20 items-center">
          <div className="flex-1 border border-white/50 rounded-full py-2 px-4 text-sm text-white/80">
            שלח הודעה...
          </div>
          <Heart size={24} className="hover:text-red-500 cursor-pointer drop-shadow-md" />
          <Share2 size={24} className="hover:text-blue-400 cursor-pointer drop-shadow-md" />
        </div>
      </div>
    );
  };

  const tabs = [
    { id: 'instagram', icon: <Camera size={18} />, label: 'Instagram' },
    { id: 'facebook', icon: <MessageCircle size={18} />, label: 'Facebook' },
    { id: 'tiktok', icon: <Video size={18} />, label: 'TikTok' },
    { id: 'x', icon: <Send size={18} />, label: 'X (Twitter)' },
    { id: 'telegram', icon: <MessageCircle size={18} />, label: 'Telegram' },
    { id: 'stories', icon: <Play size={18} />, label: 'Stories' }
  ];

  return (
    <div className="flex flex-col h-full bg-slate-50/50 -m-6 p-6 min-h-[calc(100vh-theme(spacing.16))]">
      <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-100 flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
            פיד חי <span className="relative flex h-3 w-3"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span></span>
          </h2>
          <p className="text-sm text-slate-500 mt-1">צפה בתוכן שפורסם כפי שהוא נראה בפלטפורמות השונות</p>
        </div>
        
        <div className="flex p-1 bg-slate-100 rounded-lg">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === tab.id ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'}`}
            >
              {tab.icon}
              <span className="hidden lg:inline">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pb-20">
        {loading && items.length === 0 ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
          </div>
        ) : items.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-12 text-center text-slate-400 flex flex-col items-center max-w-xl mx-auto">
            <ExternalLink size={48} className="mb-4 opacity-50" />
            <h3 className="text-lg font-medium text-slate-700 mb-1">אין תוכן בפיד</h3>
            <p className="text-sm">עדיין לא פורסם תוכן בפלטפורמה זו. אשר ותזמן תוכן כדי לראות אותו כאן.</p>
          </div>
        ) : (
          <div className={`flex flex-col ${activeTab !== 'stories' ? 'gap-6' : ''}`}>
            {activeTab === 'stories' ? (
              <StoryViewer items={items} />
            ) : (
              items.map(item => (
                <div key={item.id} className="w-full">
                  {activeTab === 'facebook' && <FacebookCard item={item} />}
                  {activeTab === 'instagram' && <InstagramCard item={item} />}
                  {activeTab === 'tiktok' && <TikTokCard item={item} />}
                  {activeTab === 'x' && <XCard item={item} />}
                  {activeTab === 'telegram' && <TelegramCard item={item} />}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
