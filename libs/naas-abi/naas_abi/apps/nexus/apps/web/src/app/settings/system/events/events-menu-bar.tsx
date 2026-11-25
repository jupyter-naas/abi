'use client';

import { Menu, MenuBar, type MenuEntry } from '@/components/ui/menu';
import {
  useAdminEventsLog,
  type AdminEventsProjection,
  type AdminEventsView,
} from './admin-events-log';
import { eventForGraph } from './events-graph';

export function buildEventsFileMenu(): MenuEntry[] {
  return [{ id: 'no-file', label: 'No file actions', disabled: true }];
}

export function buildEventsEditMenu(opts: {
  canCopyJson: boolean;
  onCopyJson: () => void;
}): MenuEntry[] {
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
}): MenuEntry[] {
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
    { id: 'sep-projection', kind: 'separator' },
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
    { id: 'sep-older', kind: 'separator' },
    {
      id: 'load-older',
      label: opts.loadingOlder ? 'Loading…' : 'Load older',
      disabled: !opts.canLoadOlder || opts.loadingOlder,
      onSelect: opts.onLoadOlder,
    },
  ];
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
  const view = useAdminEventsLog((s) => s.view);
  const projection = useAdminEventsLog((s) => s.projection);
  const setView = useAdminEventsLog((s) => s.setView);
  const setProjection = useAdminEventsLog((s) => s.setProjection);
  const events = useAdminEventsLog((s) => s.events);
  const selectedUri = useAdminEventsLog((s) => s.selectedUri);
  const canCopyJson = events.length > 0;

  const copyJson = () => {
    const event = eventForGraph(events, selectedUri);
    if (!event) return;
    void navigator.clipboard.writeText(JSON.stringify(event, null, 2));
  };

  const menus: [string, string, MenuEntry[]][] = [
    ['file', 'File', buildEventsFileMenu()],
    ['edit', 'Edit', buildEventsEditMenu({ canCopyJson, onCopyJson: copyJson })],
    ['view', 'View', buildEventsViewMenu({
      view,
      projection,
      onViewChange: setView,
      onProjectionChange: setProjection,
      canLoadOlder: !loadOlderDisabled,
      loadingOlder: Boolean(loadOlderBusy),
      onLoadOlder,
    })],
  ];

  return (
    <MenuBar label="Events menus" title="Events" testId="events-menu-bar">
      {menus.map(([key, label, items]) => (
        <Menu key={key} label={label} items={items} testId={`events-menu-${key}`} itemTestIdPrefix="events-menuitem-" />
      ))}
    </MenuBar>
  );
}
