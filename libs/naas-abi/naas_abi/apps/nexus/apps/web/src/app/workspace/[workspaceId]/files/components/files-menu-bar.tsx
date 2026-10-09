'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';
import {
  ONTOLOGY_SPACING,
  type OntologySpacingValue,
} from '@/lib/ontology-spacing';
import { APP_MENU_ROW, APP_MENU_SURFACE, APP_MENU_TRIGGER } from '@/components/shell/app-menu-classes';

export type FilesViewMode = 'list' | 'grid';

export type FilesMenuBarProps = {
  isLocalFolder: boolean;
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
  /** The open folder is a system folder: nothing can be created or uploaded in it. */
  isSystemFolder: boolean;
  /** Names starting with "." — hidden unless on, and read-only either way. */
  showSystemFiles: boolean;
  onShowSystemFilesChange: (show: boolean) => void;
};

const row = APP_MENU_ROW;
const surface = APP_MENU_SURFACE;
const trigger = APP_MENU_TRIGGER;

/**
 * App menu for Files. Mounted via `<Header nav=…>` into the shell TopNav
 * app-menu slot, same pattern as Ontology / Knowledge Graph / Slides.
 */
export function FilesMenuBar({
  isLocalFolder,
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
  isSystemFolder,
  showSystemFiles,
  onShowSystemFilesChange,
}: FilesMenuBarProps) {
  const spacingLabel =
    ONTOLOGY_SPACING.find((option) => option.value === spacing)?.label ?? 'Compact';

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
      <nav className="flex shrink-0 items-center gap-1" aria-label="Files menus" data-testid="files-menu-bar">
        <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Files</span>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger className={trigger} data-testid="files-menu-file">
            File <ChevronDown size={11} />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="start" sideOffset={5} className={surface}>
              <DropdownMenu.Item
                className={row}
                disabled={isLocalFolder || isSystemFolder}
                onSelect={onNewFile}
                data-testid="files-menuitem-new-file"
              >
                New File
              </DropdownMenu.Item>
              <DropdownMenu.Item
                className={row}
                disabled={isLocalFolder || isSystemFolder}
                onSelect={onNewFolder}
                data-testid="files-menuitem-new-folder"
              >
                New Folder
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item
                className={row}
                disabled={isLocalFolder || isSystemFolder}
                onSelect={onUpload}
                data-testid="files-menuitem-upload"
              >
                Upload…
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item
                className={row}
                disabled={loading}
                onSelect={onRefresh}
                data-testid="files-menuitem-refresh"
              >
                {loading ? 'Refreshing…' : 'Refresh'}
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item
                className={row}
                onSelect={onOpenDriveSettings}
                data-testid="files-menuitem-drive-settings"
              >
                Drive settings…
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger className={trigger} data-testid="files-menu-view">
            View <ChevronDown size={11} />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="start" sideOffset={5} className={surface}>
              <DropdownMenu.Label className="px-3 py-1 text-xs text-muted-foreground">
                Layout
              </DropdownMenu.Label>
              <DropdownMenu.RadioGroup
                value={viewMode}
                onValueChange={(value) => onViewModeChange(value as FilesViewMode)}
              >
                <DropdownMenu.RadioItem value="list" className={row} data-testid="files-menuitem-list">
                  <span className="flex w-3 items-center">
                    <DropdownMenu.ItemIndicator>
                      <Check size={12} />
                    </DropdownMenu.ItemIndicator>
                  </span>
                  List
                </DropdownMenu.RadioItem>
                <DropdownMenu.RadioItem value="grid" className={row} data-testid="files-menuitem-grid">
                  <span className="flex w-3 items-center">
                    <DropdownMenu.ItemIndicator>
                      <Check size={12} />
                    </DropdownMenu.ItemIndicator>
                  </span>
                  Grid
                </DropdownMenu.RadioItem>
              </DropdownMenu.RadioGroup>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Sub>
                <DropdownMenu.SubTrigger className={row} data-testid="files-menuitem-spacing">
                  Spacing{' '}
                  <span className="ml-auto text-muted-foreground">{spacingLabel}</span>
                  <ChevronRight size={12} />
                </DropdownMenu.SubTrigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.SubContent sideOffset={4} collisionPadding={8} className={surface}>
                    <DropdownMenu.RadioGroup
                      value={spacing}
                      onValueChange={(value) => onSpacingChange(value as OntologySpacingValue)}
                    >
                      {ONTOLOGY_SPACING.map((option) => (
                        <DropdownMenu.RadioItem
                          key={option.value}
                          value={option.value}
                          className={row}
                          data-testid={`files-menuitem-spacing-${option.value}`}
                        >
                          <span className="flex w-3 items-center">
                            <DropdownMenu.ItemIndicator>
                              <Check size={12} />
                            </DropdownMenu.ItemIndicator>
                          </span>
                          {option.label}
                        </DropdownMenu.RadioItem>
                      ))}
                    </DropdownMenu.RadioGroup>
                  </DropdownMenu.SubContent>
                </DropdownMenu.Portal>
              </DropdownMenu.Sub>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.CheckboxItem
                className={row}
                checked={showSystemFiles}
                onCheckedChange={(checked) => onShowSystemFilesChange(checked === true)}
                title='Files and folders whose name starts with "." — always read-only'
                data-testid="files-menuitem-show-system-files"
              >
                <span className="flex w-3 items-center">
                  <DropdownMenu.ItemIndicator>
                    <Check size={12} />
                  </DropdownMenu.ItemIndicator>
                </span>
                Show system files
              </DropdownMenu.CheckboxItem>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </nav>
    </div>
  );
}
