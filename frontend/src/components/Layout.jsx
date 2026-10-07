import React, { useState, useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, Calendar, FileText, CheckSquare, Home, 
  Rss, FileClock, Settings, LogOut, Menu, X, Globe, ShieldAlert 
} from 'lucide-react';
import { useLanguage } from '../lib/LanguageContext';
import ErrorBoundary from './ErrorBoundary';

const SidebarLink = ({ to, icon: Icon, children, onClick }) => {
  const location = useLocation();
  const isActive = location.pathname === to || location.pathname.startsWith(to + '/');
  return (
    <Link
      to={to}
      onClick={onClick}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${isActive ? 'bg-indigo-50 text-indigo-700 font-medium shadow-sm' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}
    >
      <Icon size={20} />
      <span>{children}</span>
    </Link>
  );
};

export default function Layout() {
  const navigate = useNavigate();
  const { t, lang, setLang } = useLanguage();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [username, setUsername] = useState('User');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (payload.sub) setUsername(payload.sub);
      } catch(e) {}
    }
  }, []);
  
  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  const closeMobile = () => setMobileOpen(false);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row">
      
      {/* Mobile Header overlay */}
      <div className="md:hidden h-16 bg-white border-b border-slate-200 flex justify-between items-center px-4 sticky top-0 z-30">
        <h1 className="text-xl font-bold text-indigo-600 tracking-tight">Promopilot</h1>
        <button onClick={() => setMobileOpen(!mobileOpen)} className="p-2 text-slate-600">
          {mobileOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Sidebar */}
      <aside className={`w-64 bg-white border-r border-slate-200 flex flex-col fixed inset-y-0 left-0 z-40 transition-transform duration-300 md:translate-x-0 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="h-16 hidden md:flex items-center px-6 border-b border-slate-200 shrink-0">
          <h1 className="text-2xl font-black text-indigo-600 tracking-tight">Promopilot<span className="text-indigo-400">.</span></h1>
        </div>
        
        <nav className="flex-1 p-4 flex flex-col gap-1 overflow-y-auto">
          <SidebarLink to="/dashboard" icon={LayoutDashboard} onClick={closeMobile}>{t('dashboard')}</SidebarLink>
          <SidebarLink to="/calendar" icon={Calendar} onClick={closeMobile}>{t('calendar')}</SidebarLink>
          <SidebarLink to="/content" icon={FileText} onClick={closeMobile}>{t('content')}</SidebarLink>
          <SidebarLink to="/approvals" icon={CheckSquare} onClick={closeMobile}>{t('approvals')}</SidebarLink>
          <SidebarLink to="/properties" icon={Home} onClick={closeMobile}>{t('properties')}</SidebarLink>
          <SidebarLink to="/feeds" icon={Rss} onClick={closeMobile}>{t('feeds')}</SidebarLink>
          <SidebarLink to="/logs" icon={FileClock} onClick={closeMobile}>{t('logs')}</SidebarLink>
          <SidebarLink to="/settings" icon={Settings} onClick={closeMobile}>{t('settings')}</SidebarLink>
        </nav>
        
        <div className="p-4 border-t border-slate-200 shrink-0">
          <button 
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-3 w-full text-slate-600 hover:bg-rose-50 hover:text-rose-700 rounded-lg transition-colors text-start cursor-pointer font-medium"
          >
            <LogOut size={20} />
            <span>{t('logout')}</span>
          </button>
        </div>
      </aside>

      {/* Backdrop for mobile */}
      {mobileOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/50 z-30 md:hidden backdrop-blur-sm transition-opacity"
          onClick={closeMobile}
        />
      )}
      
      {/* Main Content Area */}
      <main className="flex-1 md:ml-64 flex flex-col min-h-screen relative w-full max-w-full">
        {/* Demo Ribbon */}
        <div className="bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-bold py-1.5 px-4 text-center shadow-inner flex items-center justify-center gap-2">
          <ShieldAlert size={14} />
          {t('demo_ribbon')}
        </div>

        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 md:px-8 sticky top-0 z-20 shrink-0">
          <h2 className="font-semibold text-slate-800 text-lg hidden sm:block">
            {t('welcome')}, <span className="text-indigo-600">{username}</span> 👋
          </h2>
          <div className="flex items-center gap-4 ms-auto">
            {/* Language Toggle */}
            <div dir="ltr" className="flex items-center bg-slate-100 rounded-lg p-1 border border-slate-200">
              <button 
                onClick={() => setLang('en')}
                className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${lang === 'en' ? 'bg-white shadow-sm text-indigo-700' : 'text-slate-500 hover:text-slate-700'}`}
              >
                EN
              </button>
              <button 
                onClick={() => setLang('he')}
                className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${lang === 'he' ? 'bg-white shadow-sm text-indigo-700' : 'text-slate-500 hover:text-slate-700'}`}
              >
                HE
              </button>
            </div>

            <div className="w-9 h-9 rounded-full bg-indigo-100 border border-indigo-200 flex items-center justify-center text-indigo-700 font-bold shadow-sm select-none uppercase">
               {username.charAt(0)}
            </div>
          </div>
        </header>

        <div className="p-4 md:p-8 flex-1 overflow-x-hidden">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}
