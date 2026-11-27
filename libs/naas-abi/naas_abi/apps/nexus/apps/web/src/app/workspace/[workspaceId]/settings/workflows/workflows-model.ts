import { authFetch } from '@/stores/auth';

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

/** The rows by module then name: the order rows that tie on the sorted column keep. */
export function sortedWorkflows(items: WorkflowSetting[]): WorkflowSetting[] {
  return [...items].sort(
    (a, b) =>
      a.module_id.localeCompare(b.module_id) ||
      a.display_name.toLowerCase().localeCompare(b.display_name.toLowerCase())
  );
}

/** The columns of the table: each sorts and filters, as Settings › Users. */
export type WorkflowColumnId = 'name' | 'type' | 'module';
export const WORKFLOW_COLUMNS: { id: WorkflowColumnId; label: string }[] = [
  { id: 'name', label: 'Name' },
  { id: 'type', label: 'Type' },
  { id: 'module', label: 'Module' },
];

/** What a column filter sees of a row. */
export function workflowCellValues(item: WorkflowSetting, column: WorkflowColumnId): string[] {
  if (column === 'name') return [item.display_name];
  if (column === 'type') return [item.type];
  return [item.module_id];
}

/** What the search bar reads of a row: its names, module and description. */
export function workflowSearchTexts(item: WorkflowSetting): string[] {
  return [item.display_name, item.name, item.module_id, item.description];
}

export const WORKFLOW_EXPORT_HEADERS = ['Name', 'Key', 'Type', 'Module', 'Description'];

/** A row of the CSV / Excel export. */
export function workflowExportRow(item: WorkflowSetting): string[] {
  return [item.display_name, item.name, item.type, item.module_id, item.description];
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
