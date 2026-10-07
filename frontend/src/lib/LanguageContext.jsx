import React, { createContext, useContext, useState, useEffect } from 'react';

const translations = {
  he: {
    dashboard: 'דאשבורד',
    calendar: 'לוח שנה',
    content: 'תוכן',
    approvals: 'אישורים',
    properties: 'נכסים',
    feeds: 'פיד',
    logs: 'לוגים',
    settings: 'הגדרות',
    logout: 'התנתק',
    welcome: 'ברוך הבא',
    demo_ribbon: 'מצב הדגמה: Facebook, Instagram, TikTok ו-X הם סימולציה מוחלטת.',
    daily_summary: 'סיכום יומי',
    content_status: 'סטטוס התוכן שלך להיום',
    website_sync: 'סנכרון אתר',
    create_plan: 'ייצר תוכנית היום',
    publish_now: 'פרסם עכשיו (Demo)',
    posts_today: 'פוסטים היום',
    stories_today: 'סטוריז היום',
    scheduled: 'מתוזמן',
    published: 'פורסם',
    awaiting_approval: 'ממתין לאישור',
    failed: 'נכשל',
    draft: 'טיוטה',
    approved: 'מאושר',
    rejected: 'נדחה',
    facebook: 'פייסבוק',
    instagram: 'אינסטגרם',
    tiktok: 'טיקטוק',
    telegram: 'טלגרם',
    post: 'פוסט',
    story: 'סטורי',
    edit: 'ערוך',
    save: 'שמור',
    cancel: 'ביטול',
    approve: 'אשר',
    reject: 'דחה',
    regenerate: 'ייצר מחדש',
    translate: 'תרגם',
    all: 'הכל',
    search: 'חיפוש...',
    no_data: 'אין נתונים',
    select_date: 'בחר תאריך',
    platform: 'פלטפורמה',
    kind: 'סוג',
    status: 'סטטוס'
  },
  en: {
    dashboard: 'Dashboard',
    calendar: 'Calendar',
    content: 'Content',
    approvals: 'Approvals',
    properties: 'Properties',
    feeds: 'Feeds',
    logs: 'Logs',
    settings: 'Settings',
    logout: 'Log Out',
    welcome: 'Welcome',
    demo_ribbon: 'Demo Mode: Facebook, Instagram, TikTok and X are simulated.',
    daily_summary: 'Daily Summary',
    content_status: 'Your content status for today',
    website_sync: 'Website Synchronization',
    create_plan: 'Create a plan for today',
    publish_now: 'Publish Now (Demo)',
    posts_today: 'Today\'s posts',
    stories_today: 'Stories today',
    scheduled: 'Scheduled',
    published: 'Published',
    awaiting_approval: 'Awaiting approval',
    failed: 'Failed',
    draft: 'Draft',
    approved: 'Approved',
    rejected: 'Rejected',
    facebook: 'Facebook',
    instagram: 'Instagram',
    tiktok: 'TikTok',
    telegram: 'Telegram',
    post: 'Post',
    story: 'Story',
    edit: 'Edit',
    save: 'Save',
    cancel: 'Cancel',
    approve: 'Approve',
    reject: 'Reject',
    regenerate: 'Regenerate',
    translate: 'Translate',
    all: 'All',
    search: 'Search...',
    no_data: 'No Data',
    select_date: 'Select Date',
    platform: 'Platform',
    kind: 'Kind',
    status: 'Status'
  }
};

const LanguageContext = createContext();


export const LanguageProvider = ({ children }) => {
  const [lang, setLang] = useState(localStorage.getItem('lang') || 'he');

  useEffect(() => {
    localStorage.setItem('lang', lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = 'ltr'; // Hardcode to LTR to stop layout mirroring
  }, [lang]);

  const t = (key) => translations[lang][key] || key;

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => useContext(LanguageContext);
