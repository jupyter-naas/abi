/**
 * Settings › Files as a table, laid out as Settings › Users: one row per kind of files (Workspace,
 * Organization, Platform, System, My Files), in that order, each with the access the workspace gives
 * it. Pure: the view is `workspace-files.tsx`, which keeps the page a form (Save, unsaved bar).
 */

export type FilesChoice = { value: string; label: string; hint?: string; disabled?: boolean };

export type FilesRow = {
  key: string;
  label: string;
  /** What these files are, under the name. */
  description: string;
  /** The access picked (the draft's, else what is saved); none for a row shown only. */
  value: string | null;
  choices: FilesChoice[];
  editable: boolean;
  reason: string | null;
  /** Its place in the page's order: Workspace first, My Files last. */
  order: number;
};

/** What each section of files is, under its name. */
export const FILES_DESCRIPTIONS: Record<string, string> = {
  org_files: "The organization's shared files",
  platform_files: 'Files shared across the platform',
  system_files: "The deployment's own files, read only",
};

export type FilesColumnId = 'files' | 'access';
export const FILES_COLUMNS: { id: FilesColumnId; label: string }[] = [
  { id: 'files', label: 'Files' },
  { id: 'access', label: 'Access' },
];

/** The access a row gives, in words. */
export function accessLabel(row: FilesRow): string {
  if (row.choices.length === 0) return row.description;
  return row.choices.find((choice) => choice.value === row.value)?.label ?? '';
}

export function filesCellValues(row: FilesRow, column: FilesColumnId): string[] {
  return column === 'files' ? [row.label] : [accessLabel(row)];
}

/** Files sort in the page's order (Workspace first), not A to Z. */
export function filesSortValue(row: FilesRow, column: FilesColumnId): string | number {
  return column === 'files' ? row.order : accessLabel(row);
}

export function filesSearchTexts(row: FilesRow): string[] {
  return [row.label, row.description, accessLabel(row)];
}

export const FILES_EXPORT_HEADERS = ['Files', 'Access', 'Description'];
export function filesExportRow(row: FilesRow): string[] {
  return [row.label, row.choices.length ? accessLabel(row) : '', row.description];
}
