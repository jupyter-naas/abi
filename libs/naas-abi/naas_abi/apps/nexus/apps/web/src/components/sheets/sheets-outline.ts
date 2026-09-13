import { authFetch } from '@/stores/auth';
import { sheetsApiErrorMessage } from '@/lib/create-sheets-project';

export type SlideLayout = 'cover' | 'section-divider' | 'content';

export type SlideOutlineItem = {
  index: number;
  id: string | null;
  title: string;
  layout: SlideLayout;
};

export type SlideMutationResult = {
  ok: boolean;
  section_index: number;
  section_count: number;
  ids?: Array<string | null>;
  html?: string;
  sheets?: SlideOutlineItem[];
};

export const SLIDE_LAYOUTS: { id: SlideLayout; label: string }[] = [
  { id: 'content', label: 'Content' },
  { id: 'cover', label: 'Cover' },
  { id: 'section-divider', label: 'Section' },
];

const SECTION_RE = /<section\b([^>]*)>([\s\S]*?)<\/section>/gi;
const ID_RE = /\bid\s*=\s*["']([^"']+)["']/i;
const CLASS_RE = /\bclass\s*=\s*["']([^"']+)["']/i;
const LAYOUT_RE = /\bdata-layout\s*=\s*["']([^"']+)["']/i;
const H1_RE = /<h1\b[^>]*>([\s\S]*?)<\/h1>/i;
const DIVIDER_TITLE_RE =
  /<div\b[^>]*class=["'][^"']*\bdivider-title\b[^"']*["'][^>]*>([\s\S]*?)<\/div>/i;
const TAG_RE = /<[^>]+>/g;

function stripTags(raw: string): string {
  return raw.replace(TAG_RE, '').replace(/\s+/g, ' ').trim();
}

function decodeEntities(raw: string): string {
  return raw
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

export function slideLayoutFromAttrs(attrs: string): SlideLayout {
  const layout = LAYOUT_RE.exec(attrs || '')?.[1]?.trim().toLowerCase();
  if (layout === 'cover' || layout === 'section-divider' || layout === 'content') {
    return layout;
  }
  if (layout === 'blank') return 'content';
  if (layout === 'divider' || layout === 'section') return 'section-divider';
  const classes = (CLASS_RE.exec(attrs || '')?.[1] || '').toLowerCase().split(/\s+/);
  if (classes.includes('cover')) return 'cover';
  if (classes.includes('section-divider')) return 'section-divider';
  return 'content';
}

export function parseSheetsOutline(html: string): SlideOutlineItem[] {
  if (!html) return [];
  SECTION_RE.lastIndex = 0;
  const sheets: SlideOutlineItem[] = [];
  let match: RegExpExecArray | null;
  while ((match = SECTION_RE.exec(html))) {
    const attrs = match[1] || '';
    const body = match[2] || '';
    const h1 = H1_RE.exec(body)?.[1];
    const divider = DIVIDER_TITLE_RE.exec(body)?.[1];
    const title = decodeEntities(stripTags(h1 || divider || ''));
    sheets.push({
      index: sheets.length,
      id: ID_RE.exec(attrs)?.[1] || null,
      title,
      layout: slideLayoutFromAttrs(attrs),
    });
  }
  return sheets;
}

export function clampSlideIndex(index: number, count: number): number {
  if (count <= 0) return 0;
  if (index < 0) return 0;
  if (index >= count) return count - 1;
  return index;
}

async function postSlideMutation(
  workspaceId: string,
  slug: string,
  action: 'insert' | 'delete' | 'duplicate' | 'reorder',
  body: Record<string, unknown>,
): Promise<SlideMutationResult> {
  const res = await authFetch(
    `/api/sheets/projects/${encodeURIComponent(slug)}/sheets/${action}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: workspaceId, ...body }),
    },
  );
  const payload = (await res.json().catch(() => ({}))) as SlideMutationResult & {
    detail?: unknown;
  };
  if (!res.ok) {
    throw new Error(sheetsApiErrorMessage(payload.detail, `Slide ${action} failed (${res.status})`));
  }
  return payload;
}

export function insertSlide(
  workspaceId: string,
  slug: string,
  afterIndex: number,
  layout: SlideLayout,
  title = '',
): Promise<SlideMutationResult> {
  return postSlideMutation(workspaceId, slug, 'insert', {
    after_index: afterIndex,
    layout,
    title,
  });
}

export function deleteSlide(
  workspaceId: string,
  slug: string,
  index: number,
): Promise<SlideMutationResult> {
  return postSlideMutation(workspaceId, slug, 'delete', { index });
}

export function duplicateSlide(
  workspaceId: string,
  slug: string,
  index: number,
): Promise<SlideMutationResult> {
  return postSlideMutation(workspaceId, slug, 'duplicate', { index });
}

export function reorderSheets(
  workspaceId: string,
  slug: string,
  fromIndex: number,
  toIndex: number,
): Promise<SlideMutationResult> {
  return postSlideMutation(workspaceId, slug, 'reorder', {
    from_index: fromIndex,
    to_index: toIndex,
  });
}
