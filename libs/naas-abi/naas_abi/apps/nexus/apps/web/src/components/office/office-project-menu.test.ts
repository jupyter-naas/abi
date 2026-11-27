import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { OFFICE_KINDS } from './office-kinds';
import { OfficeProjectMenu, officeProjectMenuItems } from './office-project-menu';

describe('officeProjectMenuItems', () => {
  it('uses the chat strings Rename and Archive, nothing else', () => {
    const items = officeProjectMenuItems({ onRename: () => {}, onArchive: () => {} });
    const labels = items.map((item) => ('label' in item ? item.label : null));
    expect(labels).toEqual(['Rename', 'Archive']);
    expect(labels).not.toContain('Delete');
    expect(labels).not.toContain('Pin');
  });

  it('runs the matching handler on select', () => {
    const onRename = vi.fn();
    const onArchive = vi.fn();
    for (const item of officeProjectMenuItems({ onRename, onArchive })) {
      if (!item.kind || item.kind === 'item') item.onSelect?.();
    }
    expect(onRename).toHaveBeenCalledOnce();
    expect(onArchive).toHaveBeenCalledOnce();
  });
});

describe.each(OFFICE_KINDS)('OfficeProjectMenu ($id)', (kind) => {
  it('hides the menu until the kebab is open', () => {
    const html = renderToStaticMarkup(
      createElement(OfficeProjectMenu, {
        kind,
        open: false,
        onOpenChange: vi.fn(),
        onRename: vi.fn(),
        onArchive: vi.fn(),
      }),
    );
    expect(html).toContain(`data-testid="${kind.id}-project-menu"`);
    expect(html).toContain('aria-label="More actions"');
    expect(html).not.toContain('Rename');
  });
});
