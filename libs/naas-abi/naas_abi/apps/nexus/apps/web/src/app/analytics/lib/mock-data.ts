import type { AnalyticsEvent, EventName } from './types';

const USERS = [
  { id: 'u_001', email: 'alice@naas.ai', name: 'Alice Chen' },
  { id: 'u_002', email: 'bob@naas.ai', name: 'Bob Martin' },
  { id: 'u_003', email: 'carol@naas.ai', name: 'Carol Diaz' },
  { id: 'u_004', email: 'david@naas.ai', name: 'David Kim' },
  { id: 'u_005', email: 'emma@naas.ai', name: 'Emma Singh' },
  { id: 'u_006', email: 'fred@naas.ai', name: 'Fred Johnson' },
  { id: 'u_007', email: 'gina@naas.ai', name: 'Gina Williams' },
  { id: 'u_008', email: 'hugo@naas.ai', name: 'Hugo Lefebvre' },
  { id: 'u_009', email: 'iris@naas.ai', name: 'Iris Tanaka' },
  { id: 'u_010', email: 'jack@naas.ai', name: 'Jack O\'Brien' },
  { id: 'u_011', email: 'kate@naas.ai', name: 'Kate Adams' },
  { id: 'u_012', email: 'liam@naas.ai', name: 'Liam Murphy' },
];

const WORKSPACES = [
  { id: 'ws_growth', name: 'Growth' },
  { id: 'ws_ops', name: 'Operations' },
  { id: 'ws_research', name: 'Research' },
  { id: 'ws_finance', name: 'Finance' },
  { id: 'ws_intel', name: 'Intelligence' },
];

const PAGES = [
  { path: '/chat', title: 'Chat' },
  { path: '/files', title: 'Files' },
  { path: '/graph', title: 'Knowledge Graph' },
  { path: '/ontology', title: 'Ontology' },
  { path: '/marketplace', title: 'Marketplace' },
  { path: '/apps', title: 'Apps' },
  { path: '/settings/agents', title: 'Agents' },
  { path: '/settings/models', title: 'Models' },
  { path: '/settings/members', title: 'Members' },
  { path: '/lab', title: 'Lab' },
  { path: '/search', title: 'Search' },
  { path: '/organization', title: 'Organization' },
];

const DEVICES = ['Mac', 'Windows', 'iPhone', 'Linux'];
const BROWSERS = ['Chrome', 'Safari', 'Firefox', 'Edge'];
const COUNTRIES = ['US', 'FR', 'UK', 'DE', 'JP', 'CA', 'IN', 'BR'];
const REFERRERS = ['direct', 'google.com', 'linkedin.com', 'twitter.com', 'github.com'];

const EVENT_WEIGHTS: { name: EventName; weight: number }[] = [
  { name: 'page_viewed', weight: 50 },
  { name: 'button_clicked', weight: 20 },
  { name: 'search_performed', weight: 8 },
  { name: 'workspace_opened', weight: 6 },
  { name: 'file_uploaded', weight: 4 },
  { name: 'export_clicked', weight: 3 },
  { name: 'invite_sent', weight: 2 },
  { name: 'workspace_updated', weight: 2 },
  { name: 'workspace_created', weight: 1 },
  { name: 'error_seen', weight: 2 },
  { name: 'login', weight: 1 },
  { name: 'logout', weight: 1 },
];

function mulberry32(seed: number) {
  let t = seed;
  return () => {
    t |= 0;
    t = (t + 0x6d2b79f5) | 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function pick<T>(rng: () => number, arr: T[]): T {
  return arr[Math.floor(rng() * arr.length)];
}

function weightedPick<T extends { weight: number }>(rng: () => number, arr: T[]): T {
  const total = arr.reduce((s, x) => s + x.weight, 0);
  let r = rng() * total;
  for (const x of arr) {
    r -= x.weight;
    if (r <= 0) return x;
  }
  return arr[arr.length - 1];
}

function uid(rng: () => number, prefix: string): string {
  return `${prefix}_${Math.floor(rng() * 0xffffffff).toString(16).padStart(8, '0')}`;
}

let cachedEvents: AnalyticsEvent[] | null = null;

export function getMockEvents(): AnalyticsEvent[] {
  if (cachedEvents) return cachedEvents;

  const rng = mulberry32(42);
  const now = Date.now();
  const events: AnalyticsEvent[] = [];

  // Generate 60 days of data
  for (let dayOffset = 60; dayOffset >= 0; dayOffset--) {
    const dayStart = now - dayOffset * 24 * 60 * 60 * 1000;
    // Random daily activity, weekends lighter
    const dayOfWeek = new Date(dayStart).getDay();
    const weekendFactor = dayOfWeek === 0 || dayOfWeek === 6 ? 0.4 : 1;
    // Recent days have higher activity (growing usage)
    const growthFactor = 0.5 + (60 - dayOffset) / 60;
    const sessionsToday = Math.floor((6 + rng() * 14) * weekendFactor * growthFactor);

    for (let s = 0; s < sessionsToday; s++) {
      const user = pick(rng, USERS);
      const workspace = pick(rng, WORKSPACES);
      const device = pick(rng, DEVICES);
      const browser = pick(rng, BROWSERS);
      const country = pick(rng, COUNTRIES);
      const referrer = pick(rng, REFERRERS);
      const sessionId = uid(rng, 'sess');

      // Session starts somewhere during the day
      const sessionStart = dayStart + rng() * 22 * 60 * 60 * 1000;
      const sessionDurationMin = 2 + rng() * 45;

      // session_started
      events.push({
        event_id: uid(rng, 'evt'),
        timestamp: new Date(sessionStart).toISOString(),
        user_id: user.id,
        user_email: user.email,
        workspace_id: workspace.id,
        workspace_name: workspace.name,
        session_id: sessionId,
        event_name: 'session_started',
        device,
        browser,
        country,
        referrer,
      });

      // 4-25 events in the session
      const eventCount = 4 + Math.floor(rng() * 22);
      for (let i = 0; i < eventCount; i++) {
        const eventName = weightedPick(rng, EVENT_WEIGHTS).name;
        const t = sessionStart + ((i + 1) / (eventCount + 1)) * sessionDurationMin * 60 * 1000;

        const e: AnalyticsEvent = {
          event_id: uid(rng, 'evt'),
          timestamp: new Date(t).toISOString(),
          user_id: user.id,
          user_email: user.email,
          workspace_id: workspace.id,
          workspace_name: workspace.name,
          session_id: sessionId,
          event_name: eventName,
          device,
          browser,
          country,
          referrer,
        };

        if (eventName === 'page_viewed') {
          const page = pick(rng, PAGES);
          e.page_path = page.path;
          e.page_title = page.title;
        }
        if (eventName === 'button_clicked') {
          e.properties = { label: pick(rng, ['Save', 'Run', 'Export', 'Open', 'Cancel', 'Submit']) };
        }
        if (eventName === 'search_performed') {
          e.properties = { query: pick(rng, ['revenue', 'pipeline', 'agents', 'ontology', 'graph']) };
        }

        events.push(e);
      }

      // session_ended
      events.push({
        event_id: uid(rng, 'evt'),
        timestamp: new Date(sessionStart + sessionDurationMin * 60 * 1000).toISOString(),
        user_id: user.id,
        user_email: user.email,
        workspace_id: workspace.id,
        workspace_name: workspace.name,
        session_id: sessionId,
        event_name: 'session_ended',
        device,
        browser,
        country,
        referrer,
      });
    }
  }

  events.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  cachedEvents = events;
  return events;
}

export const MOCK_USERS = USERS;
export const MOCK_WORKSPACES = WORKSPACES;
