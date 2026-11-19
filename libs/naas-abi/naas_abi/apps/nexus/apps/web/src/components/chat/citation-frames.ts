/**
 * How the chat view frames a URL an answer cites (its text, a tool's output or
 * a source): text an agent read or produced chooses these URLs.
 *
 * - A URL of this app or of the API is never framed: a page there would run as
 *   the app. It opens in a new tab instead.
 * - The hidden frame that probes whether a site may be embedded is fully
 *   sandboxed (`sandbox=""`): no script, and an origin of its own.
 * - The preview panel lets a page run, never with the app's origin (no
 *   `allow-same-origin`).
 */

export const PROBE_FRAME_SANDBOX = '';
export const PREVIEW_FRAME_SANDBOX = 'allow-scripts allow-forms allow-popups';

/** This app's origin and the API's: the origins whose pages are never framed. */
export function appOrigins(apiBase: string, here: string = window.location.href): string[] {
  const origins = [new URL(here).origin];
  try {
    origins.push(new URL(apiBase, here).origin);
  } catch {
    // An API base that is no URL names no other origin.
  }
  return origins;
}

/** Whether `url` is on one of `origins`; anything that is no http(s) URL counts as one. */
export function isAppOrigin(url: string, origins: readonly string[]): boolean {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return true;
    return origins.includes(parsed.origin);
  } catch {
    return true;
  }
}

/** The hidden, fully sandboxed frame of the embeddability probe (not attached yet). */
export function createProbeFrame(url: string, doc: Document = document): HTMLIFrameElement {
  const iframe = doc.createElement('iframe');
  iframe.setAttribute('sandbox', PROBE_FRAME_SANDBOX);
  iframe.setAttribute('referrerpolicy', 'no-referrer');
  iframe.style.cssText =
    'position:fixed;left:-9999px;width:0;height:0;opacity:0;pointer-events:none;border:none;';
  iframe.src = url;
  return iframe;
}
