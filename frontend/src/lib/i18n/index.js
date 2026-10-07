import common from './common';
import layout from './layout';
import dashboard from './dashboard';
import properties from './properties';
import approvals from './approvals';
import content from './content';
import feeds from './feeds';
import calendar from './calendar';
import logs from './logs';
import settings from './settings';
import login from './login';

const parts = [common, layout, dashboard, properties, approvals, content, feeds, calendar, logs, settings, login];

const messages = { en: {}, he: {} };
for (const part of parts) {
  Object.assign(messages.en, part.en);
  Object.assign(messages.he, part.he);
}

export default messages;
