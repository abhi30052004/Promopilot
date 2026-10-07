import React from 'react';
import { useLanguage } from '../lib/LanguageContext';
import { statusTone } from '../lib/format';

export default function StatusBadge({ status, label, className = '' }) {
  const { t } = useLanguage();
  if (!status) return null;
  const key = String(status).toUpperCase();
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusTone[key] || 'bg-slate-100 text-slate-700'} ${className}`}>
      {label || t(`status.${key}`)}
    </span>
  );
}
