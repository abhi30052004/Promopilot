const actions = {
  SCRAPED: ['Property scraped', 'נכס נסרק'],
  IMAGE_STORED: ['Image stored', 'תמונה נשמרה'],
  PROPERTY_APPROVED: ['Property approved', 'נכס אושר'],
  PROPERTY_REJECTED: ['Property rejected', 'נכס נדחה'],
  CONTENT_GENERATED: ['Content generated', 'תוכן נוצר'],
  CONTENT_GENERATION_FAILED: ['Content generation failed', 'יצירת התוכן נכשלה'],
  IMAGE_GENERATION_STARTED: ['Image generation started', 'יצירת תמונה התחילה'],
  IMAGE_GENERATED: ['Image generated', 'תמונה נוצרה'],
  IMAGE_GENERATION_FAILED: ['Image generation failed', 'יצירת התמונה נכשלה'],
  VIDEO_GENERATION_STARTED: ['Video generation started', 'יצירת סרטון התחילה'],
  VIDEO_GENERATED: ['Video generated', 'סרטון נוצר'],
  VIDEO_GENERATION_FAILED: ['Video generation failed', 'יצירת הסרטון נכשלה'],
  CONTENT_APPROVED: ['Content approved', 'תוכן אושר'],
  CONTENT_REJECTED: ['Content rejected', 'תוכן נדחה'],
  POST_PUBLISHED: ['Post published', 'פוסט פורסם'],
  POST_SCHEDULED: ['Post scheduled', 'פוסט תוזמן'],
  POST_FAILED: ['Post failed', 'הפרסום נכשל'],
  AUTO_APPROVED: ['Auto-approved', 'אושר אוטומטית'],
  MODE_CHANGED: ['Mode changed', 'המצב שונה'],
  SCRAPE_FAILED: ['Scrape failed', 'הסריקה נכשלה'],
};

const en = {
  'logs.title': 'Logs',
  'logs.subtitle': 'Audit trail of every action in the system.',
  'logs.filter.action': 'Action',
  'logs.filter.platform': 'Platform',
  'logs.filter.all_actions': 'All actions',
  'logs.filter.all_platforms': 'All platforms',
  'logs.auto_refresh': 'Auto-refresh',
  'logs.col.time': 'Time',
  'logs.col.action': 'Action',
  'logs.col.entity': 'Entity',
  'logs.col.status': 'Status',
  'logs.col.mode': 'Mode',
  'logs.col.language': 'Language',
  'logs.col.platform': 'Platform',
  'logs.col.error': 'Error',
  'logs.empty': 'No log events match these filters.',
  'logs.count': '{n} events',
  'logs.load_failed': 'Could not load logs.',
};

const he = {
  'logs.title': 'יומן אירועים',
  'logs.subtitle': 'תיעוד של כל פעולה במערכת.',
  'logs.filter.action': 'פעולה',
  'logs.filter.platform': 'פלטפורמה',
  'logs.filter.all_actions': 'כל הפעולות',
  'logs.filter.all_platforms': 'כל הפלטפורמות',
  'logs.auto_refresh': 'רענון אוטומטי',
  'logs.col.time': 'זמן',
  'logs.col.action': 'פעולה',
  'logs.col.entity': 'ישות',
  'logs.col.status': 'סטטוס',
  'logs.col.mode': 'מצב',
  'logs.col.language': 'שפה',
  'logs.col.platform': 'פלטפורמה',
  'logs.col.error': 'שגיאה',
  'logs.empty': 'אין אירועים התואמים לסינון.',
  'logs.count': '{n} אירועים',
  'logs.load_failed': 'לא ניתן לטעון את היומן.',
};

for (const [code, [e, h]] of Object.entries(actions)) {
  en[`logs.action.${code}`] = e;
  he[`logs.action.${code}`] = h;
}

export const LOG_ACTIONS = Object.keys(actions);
export default { en, he };
