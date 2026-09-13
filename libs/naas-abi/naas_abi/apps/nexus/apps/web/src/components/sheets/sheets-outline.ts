import { authFetch } from '@/stores/auth';
import { sheetsApiErrorMessage } from '@/lib/create-sheets-project';

/** One sheet tab in the workbook (sidebar tab strip). */
export type SheetTabItem = {
  index: number;
  id: string | null;
  title: string;
};

export type TabMutationResult = {
  ok: boolean;
  section_index: number;
  section_count: number;
  ids?: Array<string | null>;
  html?: string;
  sheets?: SheetTabItem[];
};

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

/** Tab list from the live workbook HTML (JSON block). */
export function parseWorkbookTabs(html: string): SheetTabItem[] {
  const model = parseWorkbookModel(html);
  if (!model) return [];
  return model.sheets.map((tab, index) => ({
    index,
    id: null,
    title: tab.name,
  }));
}

/** @deprecated Use parseWorkbookTabs */
export const parseSheetsOutline = parseWorkbookTabs;

export function countWorkbookTabs(html: string): number {
  return parseWorkbookTabs(html).length;
}

export function clampTabIndex(index: number, count: number): number {
  if (count <= 0) return 0;
  if (index < 0) return 0;
  if (index >= count) return count - 1;
  return index;
}

/** @deprecated Use clampTabIndex */
export const clampSlideIndex = clampTabIndex;

async function postTabMutation(
  workspaceId: string,
  slug: string,
  action: 'insert' | 'delete' | 'duplicate' | 'reorder',
  body: Record<string, unknown>,
): Promise<TabMutationResult> {
  const res = await authFetch(
    `/api/sheets/projects/${encodeURIComponent(slug)}/sheets/${action}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: workspaceId, ...body }),
    },
  );
  const payload = (await res.json().catch(() => ({}))) as TabMutationResult & {
    detail?: unknown;
  };
  if (!res.ok) {
    throw new Error(
      sheetsApiErrorMessage(payload.detail, `Sheet tab ${action} failed (${res.status})`),
    );
  }
  return payload;
}

function mapMutationTabs(result: TabMutationResult): TabMutationResult {
  if (!result.sheets?.length) return result;
  return {
    ...result,
    sheets: result.sheets.map((row, index) => ({
      index: typeof row.index === 'number' ? row.index : index,
      id: row.id ?? null,
      title: row.title || `Sheet ${index + 1}`,
    })),
  };
}

export function insertWorkbookTab(
  workspaceId: string,
  slug: string,
  afterIndex: number,
  title = '',
): Promise<TabMutationResult> {
  return postTabMutation(workspaceId, slug, 'insert', {
    after_index: afterIndex,
    layout: 'content',
    title: title || 'Sheet',
  }).then(mapMutationTabs);
}

export function deleteWorkbookTab(
  workspaceId: string,
  slug: string,
  index: number,
): Promise<TabMutationResult> {
  return postTabMutation(workspaceId, slug, 'delete', { index }).then(mapMutationTabs);
}

export function duplicateWorkbookTab(
  workspaceId: string,
  slug: string,
  index: number,
): Promise<TabMutationResult> {
  return postTabMutation(workspaceId, slug, 'duplicate', { index }).then(mapMutationTabs);
}

export function reorderWorkbookTabs(
  workspaceId: string,
  slug: string,
  fromIndex: number,
  toIndex: number,
): Promise<TabMutationResult> {
  return postTabMutation(workspaceId, slug, 'reorder', {
    from_index: fromIndex,
    to_index: toIndex,
  }).then(mapMutationTabs);
}

/** @deprecated Use insertWorkbookTab */
export function insertSlide(
  workspaceId: string,
  slug: string,
  afterIndex: number,
  _layout: unknown,
  title = '',
): Promise<TabMutationResult> {
  return insertWorkbookTab(workspaceId, slug, afterIndex, title);
}

/** @deprecated */
export const deleteSlide = deleteWorkbookTab;
/** @deprecated */
export const duplicateSlide = duplicateWorkbookTab;
/** @deprecated */
export const reorderSheets = reorderWorkbookTabs;

export type SlideOutlineItem = SheetTabItem;
export type SlideMutationResult = TabMutationResult;
