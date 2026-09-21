'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';
import {
  ONTOLOGY_SPACING,
  type OntologySpacingValue,
} from '@/lib/ontology-spacing';

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
};

const row =
  'flex cursor-default select-none items-center gap-2 rounded-sm px-3 py-1.5 text-xs outline-none data-[highlighted]:bg-muted data-[disabled]:opacity-50';
const surface =
  'z-[300] min-w-[190px] rounded-md border border-border bg-card p-1 text-foreground shadow-lg';
const trigger =
  'flex items-center gap-1 rounded px-2 py-1 text-xs hover:bg-muted data-[state=open]:bg-muted';

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
                disabled={isLocalFolder}
                onSelect={onNewFile}
                data-testid="files-menuitem-new-file"
              >
                New File
              </DropdownMenu.Item>
              <DropdownMenu.Item
                className={row}
                disabled={isLocalFolder}
                onSelect={onNewFolder}
                data-testid="files-menuitem-new-folder"
              >
                New Folder
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item
                className={row}
                disabled={isLocalFolder}
                onSelect={onUpload}
                data-testid="files-menuitem-upload"
              >
                Upload…
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
              <DropdownMenu.Item
                className={row}
                disabled={loading}
                onSelect={onRefresh}
                data-testid="files-menuitem-refresh"
              >
                {loading ? 'Refreshing…' : 'Refresh'}
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </nav>
    </div>
  );
}
