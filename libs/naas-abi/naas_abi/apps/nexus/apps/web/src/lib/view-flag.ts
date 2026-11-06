/**
 * The browser's hint that a view ("View as") is running: a cookie that lives as long as the view
 * and holds nothing of the person. It exists because the stores and the edge middleware must know,
 * before the first request is answered, that nothing is to be read or written; the server stays the
 * authority (`GET /api/auth/oidc/session`, `view`), and a browser that disagrees with it reloads once.
 *
 * It holds the viewed workspace (where `/` lands in a view) and the page Start was pressed on (where
 * Stop returns): both the viewer's own choices. No import here: the edge middleware reads it too.
 */

export const VIEW_FLAG_COOKIE = 'nexus-view-as';

export type ViewFlag = {
  workspaceId: string;
  /** A path of this app, the person's page the view was started from. */
  returnTo: string | null;
};

/** A path on this app, never another origin. */
function localPath(value: unknown): string | null {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return null;
  return /[\u0000-\u001f]/.test(value) ? null : value;
}

/** The flag a cookie value holds; present but unreadable still means a view runs. */
export function parseViewFlag(raw: string | null | undefined): ViewFlag | null {
  if (raw === null || raw === undefined) return null;
  for (const text of [raw, safeDecode(raw)]) {
    try {
      const data = JSON.parse(text) as { workspaceId?: unknown; returnTo?: unknown };
      return {
        workspaceId: typeof data.workspaceId === 'string' ? data.workspaceId : '',
        returnTo: localPath(data.returnTo),
      };
    } catch {
      // try the decoded text, then give up
    }
  }
  return { workspaceId: '', returnTo: null };
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** The flag in a `Cookie` header or `document.cookie` text. */
export function viewFlagFromCookies(cookies: string | null | undefined): ViewFlag | null {
  if (!cookies) return null;
  for (const part of cookies.split(';')) {
    const at = part.indexOf('=');
    if (at > 0 && part.slice(0, at).trim() === VIEW_FLAG_COOKIE) return parseViewFlag(part.slice(at + 1).trim());
  }
  return null;
}

function cookieText(): string {
  try {
    return typeof document === 'undefined' ? '' : (document.cookie ?? '');
  } catch {
    return '';
  }
}

/** The flag this browser holds, or null when no view runs. */
export function readViewFlag(): ViewFlag | null {
  return viewFlagFromCookies(cookieText());
}

/** Whether a view runs: the stores neither read nor write what the browser keeps. */
export function viewFlagActive(): boolean {
  return readViewFlag() !== null;
}

/** Raise the flag until `endsAt` (the cookie expires with the view). */
export function setViewFlag(flag: ViewFlag, endsAt: string | number | Date, now: number = Date.now()): void {
  if (typeof document === 'undefined') return;
  const seconds = Math.max(1, Math.ceil((new Date(endsAt).getTime() - now) / 1000));
  const value = encodeURIComponent(JSON.stringify(flag));
  document.cookie = `${VIEW_FLAG_COOKIE}=${value}; path=/; max-age=${Number.isFinite(seconds) ? seconds : 900}; SameSite=Lax`;
}

export function clearViewFlag(): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${VIEW_FLAG_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}
