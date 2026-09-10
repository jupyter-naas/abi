import { authFetch } from '@/stores/auth';
import { documentsApiErrorMessage } from '@/lib/create-documents-project';

export type SectionLayout = 'cover' | 'section-divider' | 'content';

export type SectionOutlineItem = {
  index: number;
  id: string | null;
  title: string;
  layout: SectionLayout;
};

export type SectionMutationResult = {
  ok: boolean;
  section_index: number;
  section_count: number;
  ids?: Array<string | null>;
  html?: string;
  sections?: SectionOutlineItem[];
};

export const SLIDE_LAYOUTS: { id: SectionLayout; label: string }[] = [
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

export function sectionLayoutFromAttrs(attrs: string): SectionLayout {
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

export function parseDocumentsOutline(html: string): SectionOutlineItem[] {
  if (!html) return [];
  SECTION_RE.lastIndex = 0;
  const sections: SectionOutlineItem[] = [];
  let match: RegExpExecArray | null;
  while ((match = SECTION_RE.exec(html))) {
    const attrs = match[1] || '';
    const body = match[2] || '';
    const h1 = H1_RE.exec(body)?.[1];
    const divider = DIVIDER_TITLE_RE.exec(body)?.[1];
    const title = decodeEntities(stripTags(h1 || divider || ''));
    sections.push({
      index: sections.length,
      id: ID_RE.exec(attrs)?.[1] || null,
      title,
      layout: sectionLayoutFromAttrs(attrs),
    });
  }
  return sections;
}

export function clampSectionIndex(index: number, count: number): number {
  if (count <= 0) return 0;
  if (index < 0) return 0;
  if (index >= count) return count - 1;
  return index;
}

async function postSectionMutation(
  workspaceId: string,
  slug: string,
  action: 'insert' | 'delete' | 'duplicate' | 'reorder',
  body: Record<string, unknown>,
): Promise<SectionMutationResult> {
  const res = await authFetch(
    `/api/documents/projects/${encodeURIComponent(slug)}/sections/${action}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: workspaceId, ...body }),
    },
  );
  const payload = (await res.json().catch(() => ({}))) as SectionMutationResult & {
    detail?: unknown;
  };
  if (!res.ok) {
    throw new Error(documentsApiErrorMessage(payload.detail, `Section ${action} failed (${res.status})`));
  }
  return payload;
}

export function insertSection(
  workspaceId: string,
  slug: string,
  afterIndex: number,
  layout: SectionLayout,
  title = '',
): Promise<SectionMutationResult> {
  return postSectionMutation(workspaceId, slug, 'insert', {
    after_index: afterIndex,
    layout,
    title,
  });
}

export function deleteSection(
  workspaceId: string,
  slug: string,
  index: number,
): Promise<SectionMutationResult> {
  return postSectionMutation(workspaceId, slug, 'delete', { index });
}

export function duplicateSection(
  workspaceId: string,
  slug: string,
  index: number,
): Promise<SectionMutationResult> {
  return postSectionMutation(workspaceId, slug, 'duplicate', { index });
}

export function reorderSections(
  workspaceId: string,
  slug: string,
  fromIndex: number,
  toIndex: number,
): Promise<SectionMutationResult> {
  return postSectionMutation(workspaceId, slug, 'reorder', {
    from_index: fromIndex,
    to_index: toIndex,
  });
}
