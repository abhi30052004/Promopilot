import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import { LanguageProvider } from './lib/LanguageContext';
import { ToastProvider } from './lib/toast';
import PageLoader from './components/PageLoader';
import TopProgress from './components/TopProgress';
import Login from './pages/Login';
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Properties = lazy(() => import('./pages/Properties'));
const Content = lazy(() => import('./pages/Content'));
const Approvals = lazy(() => import('./pages/Approvals'));
const Calendar = lazy(() => import('./pages/Calendar'));
const Feeds = lazy(() => import('./pages/Feeds'));
const Logs = lazy(() => import('./pages/Logs'));
const Settings = lazy(() => import('./pages/Settings'));

const PrivateRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

function App() {
  return (
    <LanguageProvider>
      <ToastProvider>
      <BrowserRouter>
        <TopProgress />
        <Suspense fallback={<PageLoader fullScreen />}>
        <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route path="/" element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="properties" element={<Properties />} />
          <Route path="approval" element={<Approvals key="property-approval" initialTab="properties" showTabs={false} />} />
          <Route path="ai-content" element={<Content />} />
          <Route path="review" element={<Approvals key="content-review" initialTab="content" showTabs={false} />} />
          <Route path="post-schedule" element={<Calendar />} />
          <Route path="feeds" element={<Feeds />} />
          <Route path="logs" element={<Logs />} />
          <Route path="settings" element={<Settings />} />
          <Route path="calendar" element={<Navigate to="/post-schedule" replace />} />
          <Route path="content" element={<Navigate to="/ai-content" replace />} />
          <Route path="approvals" element={<Navigate to="/review" replace />} />
        </Route>
      </Routes>
        </Suspense>
    </BrowserRouter>
      </ToastProvider>
    </LanguageProvider>
  );
}

export default App;
