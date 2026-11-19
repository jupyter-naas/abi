import type { FileView, FileViewId } from '@/lib/file-views';

/** The `scope` the files API takes for each view (unchanged by the views' new names). */
export type FilesScope =
  | 'workspace'
  | 'my_drive'
  | 'organization_drive'
  | 'platform_drive'
  | 'system_drive';

/**
 * The views of the file system, in the order the API lists them: each is a starting
 * folder of the one drive (the object storage), shown to who IAM lets in.
 */
export const FILE_VIEW_SOURCES = [
  'my-files',
  'workspace-files',
  'organization-files',
  'platform-files',
  'system-files',
] as const;

export type FileViewSource = (typeof FILE_VIEW_SOURCES)[number];

/** All Views: a root with one folder per view the caller may open. */
export const ALL_VIEWS = 'all';

/** What the Files page and sidebar show: All Views, or one view. */
export type FilesSource = FileViewSource | typeof ALL_VIEWS;

/**
 * Where the dock and Home open Files: All Views, one folder per view the caller may
 * open. A link, a starred item or the View picker still choose their own.
 */
export const FILES_ENTRY_VIEW: FilesSource = ALL_VIEWS;

const VIEW_SCOPES: Record<FileViewSource, FilesScope> = {
  'my-files': 'my_drive',
  'workspace-files': 'workspace',
  'organization-files': 'organization_drive',
  'platform-files': 'platform_drive',
  'system-files': 'system_drive',
};

const VIEW_LABELS: Record<FilesSource, string> = {
  all: 'All Views',
  'my-files': 'My Files',
  'workspace-files': 'Workspace Files',
  'organization-files': 'Organization Files',
  'platform-files': 'Platform Files',
  'system-files': 'System Files',
};

const VIEW_IDS: Record<FileViewId, FileViewSource> = {
  my_files: 'my-files',
  workspace_files: 'workspace-files',
  organization_files: 'organization-files',
  platform_files: 'platform-files',
  system_files: 'system-files',
};

/** The sources of old links and starred items, when the views were called drives. */
const LEGACY_SOURCES: Record<string, FileViewSource> = {
  'my-drive': 'my-files',
  workspace: 'workspace-files',
  'organization-drive': 'organization-files',
  'platform-drive': 'platform-files',
  'system-drive': 'system-files',
};

export function isFileViewSource(source: string): source is FileViewSource {
  return (FILE_VIEW_SOURCES as readonly string[]).includes(source);
}

/**
 * The source a link, a starred item or a caller names: a view, All Views, an old
 * drive source (`?source=my-drive|workspace|organization-drive|platform-drive|system-drive`)
 * or an API view id (`my_files`…). Null for anything else (a synced folder of old).
 */
export function filesSourceFrom(raw: string | null | undefined): FilesSource | null {
  const source = (raw ?? '').trim();
  if (!source) return null;
  if (source === ALL_VIEWS || isFileViewSource(source)) return source;
  if (source in LEGACY_SOURCES) return LEGACY_SOURCES[source];
  if (source in VIEW_IDS) return VIEW_IDS[source as FileViewId];
  return null;
}

export function sourceForFileView(id: FileViewId): FileViewSource {
  return VIEW_IDS[id];
}

/** The files API scope of a view; null for All Views, which the API does not list. */
export function filesScopeForSource(source: string): FilesScope | null {
  const view = filesSourceFrom(source);
  return view && view !== ALL_VIEWS ? VIEW_SCOPES[view] : null;
}

/**
 * Storage root of a view. Organization Files is the current workspace's
 * organization's (`organizationId`); All Views and System Files have none.
 */
export function driveRootForSource(
  source: string,
  workspaceId: string,
  authUserId?: string,
  organizationId?: string,
): string {
  const view = filesSourceFrom(source);
  if (view === 'my-files') return authUserId ? `naas_abi/my-drive/${authUserId}` : '';
  if (view === 'organization-files') {
    return organizationId ? `naas_abi/organization-drive/${organizationId}` : '';
  }
  if (view === 'platform-files') return 'naas_abi/platform-drive';
  if (view === 'workspace-files') return workspaceId ? `naas_abi/workspace-drive/${workspaceId}` : '';
  return '';
}

/** A view's name: "My Files"… ("Organization Files" is never the organization's name). */
export function viewLabel(source: string): string {
  const view = filesSourceFrom(source);
  return view ? VIEW_LABELS[view] : VIEW_LABELS.all;
}

// -- Drives -------------------------------------------------------------------

/** The Drive dropdown: All Drives, then each drive (File System, the object storage, today). */
export type FilesDrive = 'all' | 'file_system';

export const FILES_DRIVES: readonly { value: FilesDrive; label: string }[] = [
  { value: 'all', label: 'All Drives' },
  { value: 'file_system', label: 'File System' },
];

export function filesDriveFrom(raw: string): FilesDrive {
  return raw === 'file_system' ? 'file_system' : 'all';
}

/** The views of one drive (all of them under All Drives). */
export function viewsOfDrive(views: readonly FileView[], drive: FilesDrive): FileView[] {
  return drive === 'all' ? [...views] : views.filter((view) => view.drive === drive);
}

/** The View dropdown: All Views, then the views of the drive the caller may open. */
export function viewChoices(
  views: readonly FileView[],
  drive: FilesDrive,
): { value: FilesSource; label: string }[] {
  return [
    { value: ALL_VIEWS, label: VIEW_LABELS.all },
    ...viewFolders(views, drive).map((folder) => ({ value: folder.source, label: folder.label })),
  ];
}

/** All Views' folders: one per view the caller may open, each opening into its view. */
export function viewFolders(
  views: readonly FileView[],
  drive: FilesDrive,
): { source: FileViewSource; label: string }[] {
  return viewsOfDrive(views, drive)
    .filter((view) => view.id in VIEW_IDS)
    .map((view) => ({ source: VIEW_IDS[view.id], label: VIEW_LABELS[VIEW_IDS[view.id]] }));
}

/**
 * What a source opens among the views offered: itself when the caller may open it
 * (or All Views), else All Views.
 */
export function offeredSource(
  source: FilesSource,
  folders: readonly { source: FileViewSource }[],
): FilesSource {
  if (source === ALL_VIEWS) return ALL_VIEWS;
  return folders.some((folder) => folder.source === source) ? source : ALL_VIEWS;
}

function stripRoot(path: string, root: string): string | null {
  const normalized = path.replace(/^\/+|\/+$/g, '');
  if (!root) return null;
  if (normalized === root) return '';
  if (normalized.startsWith(`${root}/`)) return normalized.slice(root.length + 1);
  return null;
}

/**
 * Path relative to the view's root for breadcrumbs.
 * Strips legacy bare-workspace-id roots for backwards compatibility.
 */
export function relativeDrivePath(
  currentPath: string,
  driveRoot: string,
  source: string,
  workspaceId: string,
): string {
  const legacyRoots =
    filesSourceFrom(source) === 'workspace-files' && workspaceId ? [workspaceId] : [];
  let relativePath = (currentPath || '').replace(/^\/+|\/+$/g, '');
  for (const root of [driveRoot, ...legacyRoots]) {
    const stripped = stripRoot(relativePath, root);
    if (stripped !== null) {
      relativePath = stripped;
      break;
    }
  }
  return relativePath;
}
