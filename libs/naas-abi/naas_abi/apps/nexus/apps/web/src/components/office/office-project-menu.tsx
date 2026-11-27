'use client';

import { Archive, Edit2, MoreVertical } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Menu, type MenuEntry } from '@/components/ui/menu';
import { cn } from '@/lib/utils';
import type { OfficeKind } from './office-kinds';

/**
 * Same overflow as a chat conversation row: Rename, Archive. Pin/Delete stay off;
 * documents, workbooks and decks are git projects, not chat threads.
 *
 * Opens on the ⋯ button and, controlled through `open`, on a right-click of the row or
 * card that owns it. The kit menu portals and flips, so a gallery card's
 * `overflow-hidden` or the status footer never clips it.
 */
export function officeProjectMenuItems({
  onRename,
  onArchive,
}: {
  onRename: () => void;
  onArchive: () => void;
}): MenuEntry[] {
  return [
    { id: 'rename', label: 'Rename', icon: <Edit2 size={12} />, onSelect: onRename },
    { id: 'archive', label: 'Archive', icon: <Archive size={12} />, onSelect: onArchive },
  ];
}

export function OfficeProjectMenu({
  kind,
  open,
  onOpenChange,
  onRename,
  onArchive,
  triggerClassName,
}: {
  kind: Pick<OfficeKind, 'id'>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRename: () => void;
  onArchive: () => void;
  triggerClassName?: string;
}) {
  return (
    <div className="flex shrink-0" data-testid={`${kind.id}-project-menu`}>
      <Menu
        open={open}
        onOpenChange={onOpenChange}
        align="end"
        contentTestId={`${kind.id}-project-menu-panel`}
        items={officeProjectMenuItems({ onRename, onArchive })}
        trigger={
          <Button
            variant="ghost"
            size="icon"
            aria-label="More actions"
            className={cn('h-5 w-5 rounded', triggerClassName)}
            onClick={(event) => {
              // The ⋯ sits beside a link: never let the click reach it.
              event.preventDefault();
              event.stopPropagation();
            }}
          >
            <MoreVertical size={12} />
          </Button>
        }
      />
    </div>
  );
}
