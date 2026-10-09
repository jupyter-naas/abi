import { authFetch } from '@/stores/auth';

/**
 * Home desk wallpaper, kept in the workspace drive under `.home/`. The API
 * stages an image in `.home/tmp`, serves it for preview, then commits it to
 * `.home/background-img` and points the workspace at it. `.home` is a system
 * folder, so these endpoints — not the files API — are the only way in.
 */

const base = (workspaceId: string) => `/api/workspaces/${encodeURIComponent(workspaceId)}/background-image`;

/** Max size the API accepts; checked here too so a large file fails fast. */
export const MAX_BACKGROUND_IMAGE_BYTES = 10 * 1024 * 1024;

async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === 'string') return data.detail;
  } catch {
    // not JSON
  }
  return fallback;
}

/** Stage a local file or a URL in `.home/tmp`; returns the draft's name. */
export async function stageBackgroundImage(
  workspaceId: string,
  source: { file: File } | { url: string },
): Promise<string> {
  const body = new FormData();
  if ('file' in source) body.append('file', source.file);
  else body.append('url', source.url.trim());
  const response = await authFetch(`${base(workspaceId)}/draft`, { method: 'POST', body });
  if (!response.ok) throw new Error(await errorDetail(response, 'Could not load the image'));
  const data = (await response.json()) as { draft: string };
  return data.draft;
}

/** The staged draft as a blob (the preview endpoint needs the auth header). */
export async function fetchBackgroundDraft(workspaceId: string, draft: string): Promise<Blob> {
  const response = await authFetch(`${base(workspaceId)}/draft/${encodeURIComponent(draft)}`);
  if (!response.ok) throw new Error(await errorDetail(response, 'Could not preview the image'));
  return response.blob();
}

/**
 * The wallpaper already committed under `.home/background-img`, when the
 * workspace row has no `background_image_url`. Returns null when there is none.
 * The API writes the pointer back so the next workspace load has it.
 */
export async function fetchCurrentBackgroundImage(workspaceId: string): Promise<string | null> {
  const response = await authFetch(`${base(workspaceId)}/current`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await errorDetail(response, 'Could not load the background image'));
  const data = (await response.json()) as { background_image_url?: string | null };
  return data.background_image_url || null;
}

/** Drop the staged draft (Cancel). Best effort: the next stage clears it anyway. */
export async function discardBackgroundDraft(workspaceId: string): Promise<void> {
  try {
    await authFetch(`${base(workspaceId)}/draft`, { method: 'DELETE' });
  } catch {
    // ignore
  }
}

/**
 * Save the wallpaper: a new `draft`, or the `current` one re-framed. Returns
 * the workspace's new `background_image_url`.
 */
export async function commitBackgroundImage(
  workspaceId: string,
  target: { draft: string } | { current: string },
  framing: BackgroundFraming = DEFAULT_FRAMING,
): Promise<string> {
  const response = await authFetch(base(workspaceId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...target, x: framing.x, y: framing.y, zoom: framing.zoom }),
  });
  if (!response.ok) throw new Error(await errorDetail(response, 'Could not save the background image'));
  const data = (await response.json()) as { background_image_url?: string | null };
  if (!data.background_image_url) throw new Error('Could not save the background image');
  return data.background_image_url;
}

/** True for a wallpaper served by the API (needs the auth header, so no plain CSS url()). */
export function isApiBackgroundUrl(url: string | undefined): boolean {
  return Boolean(url && /\/api\/workspaces\/[^/]+\/background-image(\?|$)/.test(url));
}

// ---------------------------------------------------------------------------
// Framing: where the image sits on the desk. Stored in the wallpaper URL
// (`&x=&y=&z=`) so it needs no column of its own, and drawn the same way in
// the preview and on the desk (see DeskWallpaper).
// ---------------------------------------------------------------------------

/** Focal point (% of the image, 0–100) and zoom (1 = cover). */
export interface BackgroundFraming {
  x: number;
  y: number;
  zoom: number;
}

export const MIN_BACKGROUND_ZOOM = 1;
export const MAX_BACKGROUND_ZOOM = 4;
export const DEFAULT_FRAMING: BackgroundFraming = { x: 50, y: 50, zoom: 1 };

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function clampFraming(framing: BackgroundFraming): BackgroundFraming {
  return {
    x: clamp(framing.x, 0, 100),
    y: clamp(framing.y, 0, 100),
    zoom: clamp(framing.zoom, MIN_BACKGROUND_ZOOM, MAX_BACKGROUND_ZOOM),
  };
}

/**
 * Split an API wallpaper URL into the image to fetch and its framing. The
 * image URL keeps only `v`, so re-framing never refetches the image.
 * Any other URL is returned untouched, centred and unzoomed.
 */
export function parseBackgroundImageUrl(url: string | undefined): {
  imageUrl: string | undefined;
  framing: BackgroundFraming;
  /** The committed file in `.home/background-img` (API wallpapers only). */
  fileName?: string;
} {
  if (!url || !isApiBackgroundUrl(url)) return { imageUrl: url, framing: DEFAULT_FRAMING };
  const [path, query = ''] = url.split('?', 2);
  const params = new URLSearchParams(query);
  const num = (key: string, fallback: number) => {
    const value = Number(params.get(key));
    return params.has(key) && Number.isFinite(value) ? value : fallback;
  };
  const framing = clampFraming({
    x: num('x', DEFAULT_FRAMING.x),
    y: num('y', DEFAULT_FRAMING.y),
    zoom: num('z', DEFAULT_FRAMING.zoom),
  });
  const v = params.get('v');
  return { imageUrl: v ? `${path}?v=${encodeURIComponent(v)}` : path, framing, fileName: v ?? undefined };
}

/**
 * Move the focal point so the image follows a pointer drag of (dx, dy) px in
 * a `box`-sized frame. The image covers the frame (CSS `cover`), is shifted
 * by background-position, then scaled by `zoom` around the focal point; one
 * percent of focal point moves the image by (overflow·zoom + frame·(zoom−1))/100 px.
 */
export function panFraming(
  framing: BackgroundFraming,
  dx: number,
  dy: number,
  box: { width: number; height: number },
  imageAspect: number,
): BackgroundFraming {
  if (box.width <= 0 || box.height <= 0 || !(imageAspect > 0)) return framing;
  const coverWidth = Math.max(box.width, box.height * imageAspect);
  const coverHeight = Math.max(box.height, box.width / imageAspect);
  const perPercentX = ((coverWidth - box.width) * framing.zoom + box.width * (framing.zoom - 1)) / 100;
  const perPercentY = ((coverHeight - box.height) * framing.zoom + box.height * (framing.zoom - 1)) / 100;
  return clampFraming({
    ...framing,
    x: perPercentX > 0 ? framing.x - dx / perPercentX : framing.x,
    y: perPercentY > 0 ? framing.y - dy / perPercentY : framing.y,
  });
}
