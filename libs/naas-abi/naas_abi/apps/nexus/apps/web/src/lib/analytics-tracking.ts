/**
 * Lightweight, client-side analytics tracker for the Nexus app.
 *
 * Usage:
 *
 *   import { trackEvent } from '@/lib/analytics-tracking';
 *
 *   trackEvent('page_viewed', {
 *     page_path: window.location.pathname,
 *     page_title: document.title,
 *     workspace_id,
 *     workspace_name,
 *   });
 *
 * Sessions:
 *   - A session_id is generated and persisted in sessionStorage.
 *   - Sessions roll over after `INACTIVITY_MS` of no events (default 30 min).
 *
 * The helper auto-attaches: timestamp, session_id, user_id/user_email (if a
 * Nexus auth token is present in localStorage), device/browser, and referrer.
 *
 * Events are POSTed to /api/analytics/events. In offline mode (no fetch /
 * SSR) the call is a no-op.
 */

import type { AnalyticsEvent, EventName } from '@/app/analytics/lib/types';
import { getApiUrl } from '@/lib/config';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';

const SESSION_KEY = 'nexus.analytics.session_id';
const SESSION_TS_KEY = 'nexus.analytics.session_last_event_ts';
const INACTIVITY_MS = 30 * 60 * 1000;

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function getOrRotateSessionId(): string {
  if (typeof window === 'undefined') return uuid();
  try {
    const now = Date.now();
    const lastTsRaw = sessionStorage.getItem(SESSION_TS_KEY);
    const lastTs = lastTsRaw ? Number(lastTsRaw) : 0;
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id || now - lastTs > INACTIVITY_MS) {
      id = uuid();
      sessionStorage.setItem(SESSION_KEY, id);
    }
    sessionStorage.setItem(SESSION_TS_KEY, String(now));
    return id;
  } catch {
    return uuid();
  }
}

function detectDevice(): string | undefined {
  if (typeof navigator === 'undefined') return undefined;
  const ua = navigator.userAgent;
  if (/iPhone|iPad|iPod/i.test(ua)) return 'iOS';
  if (/Android/i.test(ua)) return 'Android';
  if (/Mac/i.test(ua)) return 'Mac';
  if (/Win/i.test(ua)) return 'Windows';
  if (/Linux/i.test(ua)) return 'Linux';
  return 'Unknown';
}

function detectBrowser(): string | undefined {
  if (typeof navigator === 'undefined') return undefined;
  const ua = navigator.userAgent;
  if (/Edg\//i.test(ua)) return 'Edge';
  if (/Chrome\//i.test(ua) && !/Edg\//i.test(ua)) return 'Chrome';
  if (/Firefox\//i.test(ua)) return 'Firefox';
  if (/Safari\//i.test(ua) && !/Chrome\//i.test(ua)) return 'Safari';
  return 'Unknown';
}

// Best-effort, client-side only. Derives country from the user's locale
// region (e.g. `fr-FR` → `FR`). Locale ≠ physical location, but it works
// offline and needs no third-party call. For accurate geolocation, enrich
// server-side from the request IP (e.g. `x-vercel-ip-country`).
function detectCountry(): string | undefined {
  if (typeof navigator === 'undefined') return undefined;
  try {
    const tag = navigator.language;
    if (!tag) return undefined;
    const region = new Intl.Locale(tag).region;
    return region || undefined;
  } catch {
    return undefined;
  }
}

function shortReferrer(): string | undefined {
  if (typeof document === 'undefined' || !document.referrer) return undefined;
  try {
    return new URL(document.referrer).hostname || undefined;
  } catch {
    return document.referrer;
  }
}

function getCurrentUser(): { id?: string; email?: string } {
  if (typeof window === 'undefined') return {};

  // Preferred path: read directly from the running zustand auth store. This
  // always reflects the live session, including the case where the user has
  // just logged in and persistence hasn't flushed to localStorage yet.
  try {
    const user = useAuthStore.getState().user;
    if (user?.id) return { id: user.id, email: user.email };
  } catch {
    // Store not available (e.g. very early on first render) — fall through.
  }

  // Fallback: parse the persisted snapshot from localStorage. Key matches
  // the zustand persist name in src/stores/auth.ts.
  try {
    const raw = localStorage.getItem('nexus-auth');
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    const user = parsed?.state?.user;
    if (!user) return {};
    return { id: user.id, email: user.email };
  } catch {
    return {};
  }
}

export interface TrackContext {
  workspace_id?: string;
  workspace_name?: string;
  page_path?: string;
  page_title?: string;
}

function resolveWorkspaceName(workspace_id?: string): string | undefined {
  if (!workspace_id) return undefined;
  try {
    const ws = useWorkspaceStore.getState().workspaces.find((w) => w.id === workspace_id);
    return ws?.name;
  } catch {
    return undefined;
  }
}

export function trackEvent(
  event_name: EventName,
  context: TrackContext & { properties?: Record<string, unknown> } = {},
): void {
  if (typeof window === 'undefined') return;

  const user = getCurrentUser();
  const event: AnalyticsEvent = {
    event_id: uuid(),
    timestamp: new Date().toISOString(),
    session_id: getOrRotateSessionId(),
    event_name,
    user_id: user.id,
    user_email: user.email,
    workspace_id: context.workspace_id,
    workspace_name: context.workspace_name ?? resolveWorkspaceName(context.workspace_id),
    page_path: context.page_path ?? window.location.pathname,
    page_title: context.page_title ?? document.title.split(' | ')[0],
    properties: context.properties,
    device: detectDevice(),
    browser: detectBrowser(),
    country: detectCountry(),
    referrer: shortReferrer(),
  };

  // Fire-and-forget POST to the Nexus API (port 9879 in local dev), which
  // persists through ABI's object storage service. keepalive lets events
  // sent during unload still ship.
  try {
    fetch(`${getApiUrl()}/api/analytics/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
      keepalive: true,
    }).catch(() => {
      // Swallow — tracking must never break the app.
    });
  } catch {
    // ignore
  }
}

/**
 * Convenience helper for the very common page_viewed event.
 *
 *   trackPageView({ workspace_id, workspace_name });
 */
export function trackPageView(context: TrackContext = {}): void {
  trackEvent('page_viewed', context);
}
