import { authFetch } from '@/stores/auth';
import { enabledLabel, type ModuleItem } from '@/components/settings/module-items-model';
import type { OfferKind } from '@/lib/access-model/workspace-offer';

/** A workflow or pipeline of the workspace's modules, as Settings › Workflows lists it. */
export interface WorkflowSetting {
  type: 'workflow' | 'pipeline';
  module_id: string;
  name: string;
  display_name: string;
  description: string;
}

export function workflowKey(item: Pick<WorkflowSetting, 'type' | 'module_id' | 'name'>): string {
  return `${item.type}/${item.module_id}/${item.name}`;
}

/**
 * A row of the table: a workflow or pipeline the caller may run (`listed`), or a module's one they
 * may not (disabled, or not usable by them), with what the catalog says of it; its module item
 * (`item`, the Enabled checkbox).
 */
export type WorkflowRow = WorkflowSetting & { item?: ModuleItem | null; listed?: boolean };

/** The offer kind of a row's type. */
export const workflowKind = (type: WorkflowSetting['type']): OfferKind => (type === 'pipeline' ? 'pipelines' : 'workflows');

/**
 * The rows, by module then name: the workflows and pipelines listed, then every module one
 * (`catalog`) none of them is.
 */
export function workflowRows(items: WorkflowSetting[], catalog: readonly ModuleItem[] = []): WorkflowRow[] {
  const byKey = new Map(
    catalog
      .filter((item) => item.kind === 'workflows' || item.kind === 'pipelines')
      .map((item) => [`${item.kind}|${item.module}|${item.name}`, item]),
  );
  const listed: WorkflowRow[] = items.map((setting) => {
    const key = `${workflowKind(setting.type)}|${setting.module_id}|${setting.name}`;
    const item = byKey.get(key) ?? null;
    byKey.delete(key);
    return { ...setting, item, listed: true };
  });
  const unlisted: WorkflowRow[] = [...byKey.values()].map((item) => ({
    type: item.kind === 'pipelines' ? 'pipeline' : 'workflow',
    module_id: item.module,
    name: item.name,
    display_name: item.label,
    description: '',
    item,
    listed: false,
  }));
  return sortedWorkflows([...listed, ...unlisted]);
}

/** The rows by module then name: the order rows that tie on the sorted column keep. */
export function sortedWorkflows<T extends WorkflowSetting>(items: T[]): T[] {
  return [...items].sort(
    (a, b) =>
      a.module_id.localeCompare(b.module_id) ||
      a.display_name.toLowerCase().localeCompare(b.display_name.toLowerCase())
  );
}

/** The columns of the table: each sorts and filters, as Settings › Users. */
export type WorkflowColumnId = 'name' | 'type' | 'module' | 'enabled';
export const WORKFLOW_COLUMNS: { id: WorkflowColumnId; label: string }[] = [
  { id: 'name', label: 'Name' },
  { id: 'type', label: 'Type' },
  { id: 'module', label: 'Module' },
  { id: 'enabled', label: 'Enabled' },
];

/** What a column filter sees of a row. */
export function workflowCellValues(item: WorkflowRow, column: WorkflowColumnId): string[] {
  if (column === 'name') return [item.display_name];
  if (column === 'type') return [item.type];
  if (column === 'enabled') return [enabledLabel(item.item ?? null)];
  return [item.module_id];
}

/** What the search bar reads of a row: its names, module and description. */
export function workflowSearchTexts(item: WorkflowSetting): string[] {
  return [item.display_name, item.name, item.module_id, item.description];
}

export const WORKFLOW_EXPORT_HEADERS = ['Name', 'Key', 'Type', 'Module', 'Description', 'Enabled'];

/** A row of the CSV / Excel export. */
export function workflowExportRow(item: WorkflowRow): string[] {
  return [item.display_name, item.name, item.type, item.module_id, item.description, enabledLabel(item.item ?? null)];
}

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

const settingsUrl = (workspaceId: string) =>
  `/api/workspaces/${encodeURIComponent(workspaceId)}/workflows/settings`;

async function errorOf(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // not JSON
  }
  return fallback;
}

export async function fetchWorkflowSettings(
  workspaceId: string,
  fetcher: Fetcher = authFetch
): Promise<WorkflowSetting[]> {
  const response = await fetcher(settingsUrl(workspaceId));
  if (!response.ok) {
    throw new Error(await errorOf(response, `Could not load the workflows (HTTP ${response.status}).`));
  }
  const body = (await response.json()) as { workflows?: WorkflowSetting[] };
  return body.workflows ?? [];
}
