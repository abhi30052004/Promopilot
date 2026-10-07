import { LoaderCircle } from 'lucide-react';
import { useLanguage } from '../lib/LanguageContext';

// Centered loader used while a page (route chunk) or its data is loading.
export default function PageLoader({ fullScreen = false }) {
  const { t } = useLanguage();
  return (
    <div className={`flex flex-col items-center justify-center gap-3 text-indigo-600 ${fullScreen ? 'min-h-screen bg-slate-50' : 'min-h-[50vh]'}`} role="status" aria-live="polite">
      <LoaderCircle size={40} className="animate-spin" />
      <span className="text-sm font-medium text-slate-500">{t('common.loading')}</span>
    </div>
  );
}
