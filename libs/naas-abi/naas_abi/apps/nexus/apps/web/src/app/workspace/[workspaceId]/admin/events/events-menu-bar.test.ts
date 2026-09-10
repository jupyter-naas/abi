import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  buildEventsEditMenu,
  buildEventsFileMenu,
  buildEventsViewMenu,
  EventsMenuBar,
} from './events-menu-bar';

describe('buildEventsFileMenu', () => {
  it('keeps a disabled placeholder so File is not empty', () => {
    const items = buildEventsFileMenu();
    expect(items.map((item) => item.id)).toEqual(['no-file']);
    expect(items[0].disabled).toBe(true);
    expect(items[0].label).toBe('No file actions');
  });
});

describe('buildEventsEditMenu', () => {
  it('offers Copy JSON when an event is available', () => {
    const onCopyJson = vi.fn();
    const items = buildEventsEditMenu({ canCopyJson: true, onCopyJson });
    expect(items[0].id).toBe('copy-json');
    expect(items[0].disabled).toBe(false);
    items[0].onSelect?.();
    expect(onCopyJson).toHaveBeenCalled();
  });

  it('disables Copy JSON when the log is empty', () => {
    const items = buildEventsEditMenu({ canCopyJson: false, onCopyJson: vi.fn() });
    expect(items[0].disabled).toBe(true);
  });
});

describe('buildEventsViewMenu', () => {
  it('checks Table and disables 2D / 3D until Graph is on', () => {
    const onViewChange = vi.fn();
    const onProjectionChange = vi.fn();
    const items = buildEventsViewMenu({
      view: 'table',
      projection: '2d',
      onViewChange,
      onProjectionChange,
      canLoadOlder: true,
      loadingOlder: false,
      onLoadOlder: vi.fn(),
    });
    expect(items.map((item) => item.id)).toEqual([
      'table',
      'graph',
      'json',
      'sep-projection',
      '2d',
      '3d',
      'sep-older',
      'load-older',
    ]);
    expect(items.find((item) => item.id === 'table')?.checked).toBe(true);
    expect(items.find((item) => item.id === 'graph')?.checked).toBe(false);
    expect(items.find((item) => item.id === 'json')?.checked).toBe(false);
    expect(items.find((item) => item.id === '2d')?.disabled).toBe(true);
    expect(items.find((item) => item.id === '3d')?.disabled).toBe(true);
    items.find((item) => item.id === 'graph')?.onSelect?.();
    expect(onViewChange).toHaveBeenCalledWith('graph');
  });

  it('enables 2D / 3D and checks the active projection on Graph', () => {
    const onProjectionChange = vi.fn();
    const items = buildEventsViewMenu({
      view: 'graph',
      projection: '3d',
      onViewChange: vi.fn(),
      onProjectionChange,
      canLoadOlder: false,
      loadingOlder: false,
      onLoadOlder: vi.fn(),
    });
    expect(items.find((item) => item.id === 'graph')?.checked).toBe(true);
    expect(items.find((item) => item.id === '2d')?.disabled).toBe(false);
    expect(items.find((item) => item.id === '2d')?.checked).toBe(false);
    expect(items.find((item) => item.id === '3d')?.checked).toBe(true);
    expect(items.find((item) => item.id === 'load-older')?.disabled).toBe(true);
    items.find((item) => item.id === '2d')?.onSelect?.();
    expect(onProjectionChange).toHaveBeenCalledWith('2d');
  });

  it('checks JSON and disables 2D / 3D', () => {
    const onViewChange = vi.fn();
    const items = buildEventsViewMenu({
      view: 'json',
      projection: '2d',
      onViewChange,
      onProjectionChange: vi.fn(),
      canLoadOlder: true,
      loadingOlder: false,
      onLoadOlder: vi.fn(),
    });
    expect(items.find((item) => item.id === 'json')?.checked).toBe(true);
    expect(items.find((item) => item.id === 'json')?.label).toBe('JSON');
    expect(items.find((item) => item.id === 'table')?.checked).toBe(false);
    expect(items.find((item) => item.id === 'graph')?.checked).toBe(false);
    expect(items.find((item) => item.id === '2d')?.disabled).toBe(true);
    expect(items.find((item) => item.id === '3d')?.disabled).toBe(true);
    items.find((item) => item.id === 'json')?.onSelect?.();
    expect(onViewChange).toHaveBeenCalledWith('json');
  });
});

describe('EventsMenuBar', () => {
  it('shows File Edit View in the top bar', () => {
    const html = renderToStaticMarkup(
      createElement(EventsMenuBar, {
        onLoadOlder: () => {},
      }),
    );
    expect(html).toContain('File');
    expect(html).toContain('Edit');
    expect(html).toContain('View');
    expect(html).toContain('data-testid="events-menu-file"');
    expect(html).toContain('data-testid="events-menu-edit"');
    expect(html).toContain('data-testid="events-menu-view"');
    expect(html).not.toContain('Duplicate Slide');
    expect(html).not.toContain('Manual edit');
  });
});
