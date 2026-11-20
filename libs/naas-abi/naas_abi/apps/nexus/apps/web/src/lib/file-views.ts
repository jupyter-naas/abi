/**
 * The views of the file system the caller may open from a workspace, as the API lists them
 * (`GET /api/files/views`): IAM decides each one, no workspace flag does.
 */

export type FileViewId =
  | 'my_files'
  | 'workspace_files'
  | 'organization_files'
  | 'platform_files'
  | 'system_files';

export interface FileView {
  id: FileViewId;
  /** "My Files", "Workspace Files", "Organization Files", "Platform Files", "System Files". */
  label: string;
  /** The drive it is a view of: `file_system` (the object storage), the only one today. */
  drive: string;
  /** The `scope` the files routes take for it (`my_drive`, `workspace`, …). */
  scope: string;
  /** Its folder in the drive: a storage path, `''` for the whole store (System Files). */
  root: string;
}

export function fileViewsPath(workspaceId?: string | null): string {
  return workspaceId
    ? `/api/files/views?workspace_id=${encodeURIComponent(workspaceId)}`
    : '/api/files/views';
}

function isFileView(value: unknown): value is FileView {
  if (!value || typeof value !== 'object') return false;
  const view = value as Record<string, unknown>;
  return ['id', 'label', 'drive', 'scope', 'root'].every((key) => typeof view[key] === 'string');
}

export function parseFileViews(body: unknown): FileView[] {
  const views = body && typeof body === 'object' ? (body as { views?: unknown }).views : undefined;
  return Array.isArray(views) ? views.filter(isFileView) : [];
}

export function hasFileView(views: readonly FileView[], id: FileViewId): boolean {
  return views.some((view) => view.id === id);
}
