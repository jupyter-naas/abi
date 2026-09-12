import { authFetch } from '@/stores/auth';
import { documentsApiErrorMessage } from '@/lib/create-documents-project';

export type SectionLayout = 'cover' | 'section-divider' | 'content' | 'page-break';
export type DocumentsInsertKind = 'page-break' | 'heading' | 'paragraph';

export type DocumentCommand = {
  type:
    | 'insert_page_break'
    | 'insert_heading'
    | 'insert_paragraph'
    | 'insert_text'
    | 'delete_range'
    | 'replace_text'
    | 'replace_class'
    | 'update_paragraph_style'
    | 'update_title'
    | 'rename_document';
  after_heading?: number;
  heading_index?: number;
  text?: string;
  title?: string;
  level?: number;
  style?: string;
  find?: string;
  replace?: string;
  class_name?: string;
  html?: string;
};

export const PAGE_BREAK_HTML = '<div class="page-break" data-nexus-page-break></div>';

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
  { id: 'page-break', label: 'Page break' },
  { id: 'content', label: 'Content' },
  { id: 'cover', label: 'Cover' },
  { id: 'section-divider', label: 'Section' },
];

const SECTION_RE = /<section\b([^>]*)>([\s\S]*?)<\/section>/gi;
const ID_RE = /\bid\s*=\s*["']([^"']+)["']/i;
const CLASS_RE = /\bclass\s*=\s*["']([^"']+)["']/i;
const LAYOUT_RE = /\bdata-layout\s*=\s*["']([^"']+)["']/i;
const H1_RE = /<h1\b[^>]*>([\s\S]*?)<\/h1>/i;
const H2_RE = /<h2\b[^>]*>([\s\S]*?)<\/h2>/i;
const HEADING_RE = /<h([1-3])\b[^>]*>([\s\S]*?)<\/h\1>/gi;
const HEADING_TAG_RE = /<h([1-3])\b[^>]*>[\s\S]*?<\/h\1>/gi;
const BLOCK_BOUNDARY_RE =
  /<h[1-3]\b|<(?:div\b[^>]*(?:data-nexus-page-break|class=["'][^"']*\bpage-break))|<footer\b|<\/section>|<\/main>/i;
const DOC_BODY_OPEN_RE =
  /<div\b[^>]*\bclass\s*=\s*["'][^"']*\bdoc-body\b[^"']*["'][^>]*>/gi;
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
  if (
    layout === 'cover' ||
    layout === 'section-divider' ||
    layout === 'content' ||
    layout === 'page-break'
  ) {
    return layout;
  }
  if (layout === 'blank') return 'content';
  if (layout === 'page' || layout === 'pagebreak') return 'page-break';
  if (layout === 'divider' || layout === 'section') return 'section-divider';
  const classes = (CLASS_RE.exec(attrs || '')?.[1] || '').toLowerCase().split(/\s+/);
  if (classes.includes('cover')) return 'cover';
  if (classes.includes('section-divider')) return 'section-divider';
  if (classes.includes('page-break')) return 'page-break';
  return 'content';
}

export function parseDocumentsHeadingOutline(html: string): SectionOutlineItem[] {
  if (!html) return [];
  HEADING_RE.lastIndex = 0;
  const items: SectionOutlineItem[] = [];
  let match: RegExpExecArray | null;
  while ((match = HEADING_RE.exec(html))) {
    const title = decodeEntities(stripTags(match[2] || ''));
    items.push({
      index: items.length,
      id: null,
      title: title || `Heading ${items.length + 1}`,
      layout: items.length === 0 ? 'cover' : 'content',
    });
  }
  return items;
}

export function parseDocumentsSectionOutline(html: string): SectionOutlineItem[] {
  if (!html) return [];
  SECTION_RE.lastIndex = 0;
  const sections: SectionOutlineItem[] = [];
  let match: RegExpExecArray | null;
  while ((match = SECTION_RE.exec(html))) {
    const attrs = match[1] || '';
    const body = match[2] || '';
    const h1 = H1_RE.exec(body)?.[1];
    const h2 = H2_RE.exec(body)?.[1];
    const divider = DIVIDER_TITLE_RE.exec(body)?.[1];
    const title = decodeEntities(stripTags(h1 || divider || h2 || ''));
    sections.push({
      index: sections.length,
      id: ID_RE.exec(attrs)?.[1] || null,
      title,
      layout: sectionLayoutFromAttrs(attrs),
    });
  }
  return sections;
}

/** Headings in the prose flow. Falls back to leftover section blocks. */
export function parseDocumentsOutline(html: string): SectionOutlineItem[] {
  const headings = parseDocumentsHeadingOutline(html);
  if (headings.length) return headings;
  return parseDocumentsSectionOutline(html);
}

function matchingCloseDiv(html: string, innerStart: number): number | null {
  let depth = 1;
  let pos = innerStart;
  const openRe = /<div\b/gi;
  const closeRe = /<\/div>/gi;
  while (pos < html.length) {
    openRe.lastIndex = pos;
    closeRe.lastIndex = pos;
    const opened = openRe.exec(html);
    const closed = closeRe.exec(html);
    if (!closed) return null;
    if (opened && opened.index < closed.index) {
      depth += 1;
      pos = opened.index + opened[0].length;
      continue;
    }
    depth -= 1;
    if (depth === 0) return closed.index;
    pos = closed.index + closed[0].length;
  }
  return null;
}

function docBodyRanges(html: string): Array<[number, number]> {
  const ranges: Array<[number, number]> = [];
  DOC_BODY_OPEN_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = DOC_BODY_OPEN_RE.exec(html))) {
    const close = matchingCloseDiv(html, match.index + match[0].length);
    if (close != null) ranges.push([match.index + match[0].length, close]);
  }
  return ranges;
}

function clampInsertIntoDocBody(html: string, at: number): number {
  const bodies = docBodyRanges(html);
  if (bodies.length) {
    for (const [start, close] of bodies) {
      if (start <= at && at <= close) return at;
    }
    let chosen = bodies[0];
    for (const [start, close] of bodies) {
      if (start <= at) chosen = [start, close];
    }
    return chosen[1];
  }
  const footerAt = html.slice(0, at).toLowerCase().lastIndexOf('<footer');
  if (footerAt >= 0) return footerAt;
  return at;
}

function insertAt(html: string, at: number, markup: string): string {
  const injected = markup.endsWith('\n') ? markup : `${markup}\n`;
  return `${html.slice(0, at)}\n${injected}${html.slice(at)}`;
}

function insertBeforeDocumentClose(html: string, markup: string): string {
  const bodies = docBodyRanges(html);
  if (bodies.length) {
    return insertAt(html, bodies[bodies.length - 1][1], markup);
  }
  const footer = html.toLowerCase().lastIndexOf('<footer');
  if (footer >= 0) {
    return insertAt(html, footer, markup);
  }
  const close = html.toLowerCase().lastIndexOf('</section>');
  if (close >= 0) {
    return `${html.slice(0, close)}${markup}\n${html.slice(close)}`;
  }
  const main = html.toLowerCase().lastIndexOf('</main>');
  if (main >= 0) {
    return `${html.slice(0, main)}${markup}\n${html.slice(main)}`;
  }
  return `${html}${markup}`;
}

export function insertMarkupAfterHeadingBlock(
  html: string,
  headingIndex: number,
  markup: string,
): string {
  if (!html || !markup) return html;
  HEADING_TAG_RE.lastIndex = 0;
  const ends: number[] = [];
  let match: RegExpExecArray | null;
  while ((match = HEADING_TAG_RE.exec(html))) {
    ends.push(match.index + match[0].length);
  }
  if (!ends.length) return insertBeforeDocumentClose(html, markup);
  const idx = Math.max(0, Math.min(headingIndex, ends.length - 1));
  const start = ends[idx];
  const rest = html.slice(start);
  const boundary = BLOCK_BOUNDARY_RE.exec(rest);
  const at = clampInsertIntoDocBody(
    html,
    start + (boundary ? boundary.index : rest.length),
  );
  return insertAt(html, at, markup);
}

export function insertPageBreakHtml(html: string, afterHeadingIndex: number): string {
  return insertMarkupAfterHeadingBlock(html, afterHeadingIndex, PAGE_BREAK_HTML);
}

export function insertHeadingHtml(
  html: string,
  afterHeadingIndex: number,
  title = 'Heading',
): string {
  const safe = title
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return insertMarkupAfterHeadingBlock(html, afterHeadingIndex, `<h2>${safe}</h2>\n<p></p>`);
}

export function clampSectionIndex(index: number, count: number): number {
  if (count <= 0) return 0;
  if (index < 0) return 0;
  if (index >= count) return count - 1;
  return index;
}

export async function applyDocumentCommands(
  workspaceId: string,
  slug: string,
  requests: DocumentCommand[],
): Promise<SectionMutationResult> {
  const res = await authFetch(
    `/api/documents/projects/${encodeURIComponent(slug)}/commands`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: workspaceId, requests }),
    },
  );
  const payload = (await res.json().catch(() => ({}))) as {
    ok?: boolean;
    heading_index?: number;
    heading_count?: number;
    html?: string;
    outline?: SectionOutlineItem[];
    detail?: unknown;
  };
  if (!res.ok) {
    throw new Error(
      documentsApiErrorMessage(payload.detail, `Document command failed (${res.status})`),
    );
  }
  return {
    ok: Boolean(payload.ok),
    section_index: payload.heading_index ?? 0,
    section_count: payload.heading_count ?? 0,
    html: payload.html,
    sections: payload.outline,
  };
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
