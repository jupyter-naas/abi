import { authFetch } from '@/stores/auth';
import { sheetsApiErrorMessage } from '@/lib/create-sheets-project';

/** One workbook tab (filmstrip item). Layout is kept for menu parity with Slides UI. */
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
  { id: 'content', label: 'Sheet tab' },
];

const JSON_TYPE = 'application/vnd.nexus.sheet+json';

function extractWorkbookJsonScript(html: string): string | null {
  const marker = `type="${JSON_TYPE}"`;
  const alt = `type='${JSON_TYPE}'`;
  const start = html.includes(marker)
    ? html.indexOf(marker) + marker.length
    : html.includes(alt)
      ? html.indexOf(alt) + alt.length
      : -1;
  if (start < 0) return null;
  const openEnd = html.indexOf('>', start);
  if (openEnd < 0) return null;
  const close = html.indexOf('</script>', openEnd);
  if (close < 0) return null;
  return html.slice(openEnd + 1, close).trim();
}

function parseWorkbookModel(html: string): { sheets: Array<{ name: string }> } | null {
  if (!html) return null;
  const jsonText = extractWorkbookJsonScript(html);
  if (!jsonText) return null;
  try {
    const data = JSON.parse(jsonText) as { sheets?: Array<{ name?: string }> };
    if (!Array.isArray(data.sheets)) return null;
    return { sheets: data.sheets.map((s) => ({ name: String(s.name || 'Sheet') })) };
  } catch {
    return null;
  }
}

export function parseSheetsOutline(html: string): SlideOutlineItem[] {
  const model = parseWorkbookModel(html);
  if (!model) return [];
  return model.sheets.map((tab, index) => ({
    index,
    id: null,
    title: tab.name,
    layout: 'content',
  }));
}

export function slideLayoutFromAttrs(_attrs: string): SlideLayout {
  return 'content';
}

export function clampSlideIndex(index: number, count: number): number {
  if (count <= 0) return 0;
  if (index < 0) return 0;
  if (index >= count) return count - 1;
  return index;
}

async function postTabMutation(
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
    throw new Error(
      sheetsApiErrorMessage(payload.detail, `Sheet tab ${action} failed (${res.status})`),
    );
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
  return postTabMutation(workspaceId, slug, 'insert', {
    after_index: afterIndex,
    layout,
    title: title || 'Sheet',
  });
}

export function deleteSlide(
  workspaceId: string,
  slug: string,
  index: number,
): Promise<SlideMutationResult> {
  return postTabMutation(workspaceId, slug, 'delete', { index });
}

export function duplicateSlide(
  workspaceId: string,
  slug: string,
  index: number,
): Promise<SlideMutationResult> {
  return postTabMutation(workspaceId, slug, 'duplicate', { index });
}

export function reorderSheets(
  workspaceId: string,
  slug: string,
  fromIndex: number,
  toIndex: number,
): Promise<SlideMutationResult> {
  return postTabMutation(workspaceId, slug, 'reorder', {
    from_index: fromIndex,
    to_index: toIndex,
  });
}
