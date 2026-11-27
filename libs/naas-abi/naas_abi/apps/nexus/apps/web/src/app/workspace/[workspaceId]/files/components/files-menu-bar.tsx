'use client';

import {
  ONTOLOGY_SPACING,
  type OntologySpacingValue,
} from '@/lib/ontology-spacing';
import { Menu, MenuBar, type MenuEntry } from '@/components/ui/menu';

export type FilesViewMode = 'list' | 'grid';

export type FilesMenuBarProps = {
  /** All Views is open: its folders are the views, nothing can be created or uploaded there. */
  isViewsRoot: boolean;
  loading: boolean;
  viewMode: FilesViewMode;
  onViewModeChange: (mode: FilesViewMode) => void;
  /** Same Compact / Comfortable / Spacious labels as Ontology View → Spacing. */
  spacing: OntologySpacingValue;
  onSpacingChange: (value: OntologySpacingValue) => void;
  onNewFile: () => void;
  onNewFolder: () => void;
  onUpload: () => void;
  onRefresh: () => void;
  onOpenDriveSettings: () => void;
  /** "Drive settings…" is shown only to who may open Platform settings › Drives. */
  showDriveSettings: boolean;
  /** The open folder is a system folder: nothing can be created or uploaded in it. */
  isSystemFolder: boolean;
  /** Names starting with "." — hidden unless on, and read-only either way. */
  showSystemFiles: boolean;
  onShowSystemFilesChange: (show: boolean) => void;
};

/**
 * App menu for Files. Mounted via `<Header nav=…>` into the shell TopNav
 * app-menu slot, same pattern as Ontology / Knowledge Graph / Slides.
 */
export function FilesMenuBar({
  isViewsRoot,
  loading,
  viewMode,
  onViewModeChange,
  spacing,
  onSpacingChange,
  onNewFile,
  onNewFolder,
  onUpload,
  onRefresh,
  onOpenDriveSettings,
  showDriveSettings,
  isSystemFolder,
  showSystemFiles,
  onShowSystemFilesChange,
}: FilesMenuBarProps) {
  const locked = isViewsRoot || isSystemFolder;
  const fileItems: MenuEntry[] = [
    { id: 'new-file', label: 'New File', disabled: locked, onSelect: onNewFile },
    { id: 'new-folder', label: 'New Folder', disabled: locked, onSelect: onNewFolder },
    { id: 'sep-upload', kind: 'separator' },
    { id: 'upload', label: 'Upload…', disabled: locked, onSelect: onUpload },
    { id: 'sep-refresh', kind: 'separator' },
    { id: 'refresh', label: loading ? 'Refreshing…' : 'Refresh', disabled: loading, onSelect: onRefresh },
    ...(showDriveSettings
      ? ([
          { id: 'sep-drive', kind: 'separator' },
          { id: 'drive-settings', label: 'Drive settings…', onSelect: onOpenDriveSettings },
        ] satisfies MenuEntry[])
      : []),
  ];
  const viewItems: MenuEntry[] = [
    { id: 'layout', kind: 'heading', label: 'Layout' },
    { id: 'list', label: 'List', checked: viewMode === 'list', onSelect: () => onViewModeChange('list') },
    { id: 'grid', label: 'Grid', checked: viewMode === 'grid', onSelect: () => onViewModeChange('grid') },
    { id: 'sep-spacing', kind: 'separator' },
    {
      id: 'spacing',
      kind: 'submenu',
      label: 'Spacing',
      value: ONTOLOGY_SPACING.find((option) => option.value === spacing)?.label ?? 'Compact',
      items: ONTOLOGY_SPACING.map((option) => ({
        id: `spacing-${option.value}`,
        label: option.label,
        checked: option.value === spacing,
        onSelect: () => onSpacingChange(option.value),
      })),
    },
    { id: 'sep-system', kind: 'separator' },
    {
      id: 'show-system-files',
      label: 'Show system files',
      checked: showSystemFiles,
      title: 'Files and folders whose name starts with "." — always read-only',
      onSelect: () => onShowSystemFilesChange(!showSystemFiles),
    },
  ];

  return (
    <MenuBar label="Files menus" title="Files" testId="files-menu-bar">
      <Menu label="File" testId="files-menu-file" itemTestIdPrefix="files-menuitem-" items={fileItems} />
      <Menu label="View" testId="files-menu-view" itemTestIdPrefix="files-menuitem-" items={viewItems} />
    </MenuBar>
  );
}
