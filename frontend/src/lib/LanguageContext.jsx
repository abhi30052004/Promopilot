import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import messages from './i18n';

const LanguageContext = createContext(null);

function readStoredLang() {
  try {
    const stored = localStorage.getItem('lang');
    return stored === 'he' || stored === 'en' ? stored : 'en';
  } catch {
    return 'en';
  }
}

export const LanguageProvider = ({ children }) => {
  const [lang, setLangState] = useState(readStoredLang);
  const dir = lang === 'he' ? 'rtl' : 'ltr';

  useEffect(() => {
    try { localStorage.setItem('lang', lang); } catch { /* storage may be unavailable */ }
    document.documentElement.lang = lang;
    document.documentElement.dir = dir; // real RTL layout in Hebrew
    document.documentElement.setAttribute('translate', 'no'); // browser auto-translate breaks React's DOM
  }, [lang, dir]);

  const setLang = useCallback((next) => setLangState(next === 'he' ? 'he' : 'en'), []);

  // t('key', { n: 3 }) -> translated string with {n} replaced. Falls back to English, then the key.
  const t = useCallback((key, vars) => {
    let text = messages[lang][key] ?? messages.en[key] ?? key;
    if (vars) {
      for (const [name, value] of Object.entries(vars)) {
        text = text.split(`{${name}}`).join(String(value));
      }
    }
    return text;
  }, [lang]);

  const value = useMemo(() => ({ lang, setLang, t, dir, isRTL: dir === 'rtl' }), [lang, setLang, t, dir]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
};

export const useLanguage = () => useContext(LanguageContext);
