import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { FileView } from '@/lib/file-views';
import { FilesViewPicker } from './files-view-picker';

const VIEWS: FileView[] = [
  { id: 'my_files', label: 'My Files', drive: 'file_system', scope: 'my_drive', root: 'r' },
  { id: 'workspace_files', label: 'Workspace Files', drive: 'file_system', scope: 'workspace', root: 'w' },
];

function render(props: Partial<Parameters<typeof FilesViewPicker>[0]> = {}) {
  return renderToStaticMarkup(
    createElement(FilesViewPicker, {
      views: VIEWS,
      drive: 'all',
      view: 'all',
      onDriveChange: vi.fn(),
      onViewChange: vi.fn(),
      ...props,
    }),
  );
}

describe('FilesViewPicker', () => {
  // The ontology sidebar's picker, not native selects.
  it('renders the Drive then the View picker as ontology pickers', () => {
    const html = render();
    expect(html).not.toContain('<select');
    expect(html.match(/class="search-picker-trigger/g)).toHaveLength(2);
    const drive = html.indexOf('aria-label="Choose drive: All Drives"');
    const view = html.indexOf('aria-label="Choose view: All Views"');
    expect(drive).toBeGreaterThan(-1);
    expect(view).toBeGreaterThan(drive);
  });

  it('stacks the two pickers, Drive above View, like the ontology filters', () => {
    expect(render()).toContain('class="search-picker-stack');
  });

  it('labels each trigger with its choice', () => {
    const html = render({ drive: 'file_system', view: 'workspace-files' });
    expect(html).toContain('aria-label="Choose drive: File System"');
    expect(html).toContain('aria-label="Choose view: Workspace Files"');
  });

  it('reads a view no longer offered as All Views', () => {
    expect(render({ view: 'system-files' })).toContain('aria-label="Choose view: All Views"');
  });
});
