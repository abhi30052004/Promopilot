import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import { LanguageProvider } from './lib/LanguageContext';
import { ToastProvider } from './lib/toast';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Properties from './pages/Properties';
import Content from './pages/Content';
import Approvals from './pages/Approvals';
import Calendar from './pages/Calendar';
import Feeds from './pages/Feeds';
import Logs from './pages/Logs';
import Settings from './pages/Settings';

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
    </BrowserRouter>
      </ToastProvider>
    </LanguageProvider>
  );
}

export default App;
