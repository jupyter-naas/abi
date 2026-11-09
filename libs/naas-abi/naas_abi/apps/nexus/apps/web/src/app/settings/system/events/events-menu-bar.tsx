'use client';

import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useAdminEventsLog,
  type AdminEventsProjection,
  type AdminEventsView,
} from './admin-events-log';
import { eventForGraph } from './events-graph';

type MenuKey = 'file' | 'edit' | 'view' | null;

export type EventsMenuEntry = {
  id: string;
  label?: string;
  shortcut?: string;
  disabled?: boolean;
  checked?: boolean;
  separator?: boolean;
  onSelect?: () => void;
};

function isSeparator(item: EventsMenuEntry): boolean {
  return Boolean(item.separator);
}

export function buildEventsFileMenu(): EventsMenuEntry[] {
  return [{ id: 'no-file', label: 'No file actions', disabled: true }];
}

export function buildEventsEditMenu(opts: {
  canCopyJson: boolean;
  onCopyJson: () => void;
}): EventsMenuEntry[] {
  return [
    {
      id: 'copy-json',
      label: 'Copy JSON',
      disabled: !opts.canCopyJson,
      onSelect: opts.onCopyJson,
    },
  ];
}

export function buildEventsViewMenu(opts: {
  view: AdminEventsView;
  projection: AdminEventsProjection;
  onViewChange: (view: AdminEventsView) => void;
  onProjectionChange: (projection: AdminEventsProjection) => void;
  canLoadOlder: boolean;
  loadingOlder: boolean;
  onLoadOlder: () => void;
}): EventsMenuEntry[] {
  const graphOn = opts.view === 'graph';
  return [
    {
      id: 'table',
      label: 'Table',
      checked: opts.view === 'table',
      onSelect: () => opts.onViewChange('table'),
    },
    {
      id: 'graph',
      label: 'Graph',
      checked: graphOn,
      onSelect: () => opts.onViewChange('graph'),
    },
    {
      id: 'json',
      label: 'JSON',
      checked: opts.view === 'json',
      onSelect: () => opts.onViewChange('json'),
    },
    { id: 'sep-projection', separator: true },
    {
      id: '2d',
      label: '2D',
      disabled: !graphOn,
      checked: graphOn && opts.projection === '2d',
      onSelect: () => opts.onProjectionChange('2d'),
    },
    {
      id: '3d',
      label: '3D',
      disabled: !graphOn,
      checked: graphOn && opts.projection === '3d',
      onSelect: () => opts.onProjectionChange('3d'),
    },
    { id: 'sep-older', separator: true },
    {
      id: 'load-older',
      label: opts.loadingOlder ? 'Loading…' : 'Load older',
      disabled: !opts.canLoadOlder || opts.loadingOlder,
      onSelect: opts.onLoadOlder,
    },
  ];
}

function MenuRow({ item, onClose }: { item: EventsMenuEntry; onClose: () => void }) {
  if (isSeparator(item)) {
    return <div role="separator" className="my-1 h-px bg-border" />;
  }
  return (
    <button
      type="button"
      role="menuitem"
      disabled={item.disabled}
      data-testid={`events-menuitem-${item.id}`}
      onClick={() => {
        if (item.disabled || !item.onSelect) return;
        item.onSelect();
        onClose();
      }}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors',
        item.disabled
          ? 'cursor-not-allowed text-muted-foreground/50'
          : 'hover:bg-muted',
      )}
    >
      <span className="w-3.5 shrink-0">
        {item.checked ? <Check size={12} className="text-workspace-accent" /> : null}
      </span>
      <span className="flex-1">{item.label}</span>
      {item.shortcut ? (
        <span className="text-[10px] text-muted-foreground">{item.shortcut}</span>
      ) : null}
    </button>
  );
}

function MenuDropdown({
  label,
  menuKey,
  open,
  onOpenChange,
  items,
}: {
  label: string;
  menuKey: Exclude<MenuKey, null>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: EventsMenuEntry[];
}) {
  return (
    <div className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        data-testid={`events-menu-${menuKey}`}
        onClick={() => onOpenChange(!open)}
        className={cn(
          'inline-flex items-center gap-0.5 rounded px-2 py-1 text-xs font-medium transition-colors',
          open
            ? 'bg-muted text-foreground'
            : 'text-foreground/90 hover:bg-muted hover:text-foreground',
        )}
      >
        {label}
        <ChevronDown size={12} className="opacity-60" />
      </button>
      {open && (
        <div
          role="menu"
          data-testid={`events-menu-${menuKey}-dropdown`}
          className="absolute left-0 top-full z-[300] mt-1 min-w-[12.5rem] rounded-md border border-border bg-card py-1 shadow-lg"
        >
          {items.map((item) => (
            <MenuRow key={item.id} item={item} onClose={() => onOpenChange(false)} />
          ))}
        </div>
      )}
    </div>
  );
}

export interface EventsMenuBarProps {
  onLoadOlder: () => void;
  loadOlderDisabled?: boolean;
  loadOlderBusy?: boolean;
}

export function EventsMenuBar({
  onLoadOlder,
  loadOlderDisabled,
  loadOlderBusy,
}: EventsMenuBarProps) {
  const [openMenu, setOpenMenu] = useState<MenuKey>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const view = useAdminEventsLog((s) => s.view);
  const projection = useAdminEventsLog((s) => s.projection);
  const setView = useAdminEventsLog((s) => s.setView);
  const setProjection = useAdminEventsLog((s) => s.setProjection);
  const events = useAdminEventsLog((s) => s.events);
  const selectedUri = useAdminEventsLog((s) => s.selectedUri);
  const canCopyJson = events.length > 0;

  useEffect(() => {
    const onDoc = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpenMenu(null);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const copyJson = () => {
    const event = eventForGraph(events, selectedUri);
    if (!event) return;
    void navigator.clipboard.writeText(JSON.stringify(event, null, 2));
  };

  return (
    <div ref={rootRef} className="flex min-w-0 items-center gap-1" data-testid="events-menu-bar">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Events</span>
      <MenuDropdown
        label="File"
        menuKey="file"
        open={openMenu === 'file'}
        onOpenChange={(open) => setOpenMenu(open ? 'file' : null)}
        items={buildEventsFileMenu()}
      />
      <MenuDropdown
        label="Edit"
        menuKey="edit"
        open={openMenu === 'edit'}
        onOpenChange={(open) => setOpenMenu(open ? 'edit' : null)}
        items={buildEventsEditMenu({ canCopyJson, onCopyJson: copyJson })}
      />
      <MenuDropdown
        label="View"
        menuKey="view"
        open={openMenu === 'view'}
        onOpenChange={(open) => setOpenMenu(open ? 'view' : null)}
        items={buildEventsViewMenu({
          view,
          projection,
          onViewChange: setView,
          onProjectionChange: setProjection,
          canLoadOlder: !loadOlderDisabled,
          loadingOlder: Boolean(loadOlderBusy),
          onLoadOlder,
        })}
      />
    </div>
  );
}
