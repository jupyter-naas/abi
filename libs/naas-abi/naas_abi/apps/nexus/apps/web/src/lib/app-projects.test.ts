import { describe, expect, it } from 'vitest';
import {
  APP_PROJECT_WRITE_TOOLS,
  appEditorPath,
  buildFileTree,
  isAppProjectWriteTool,
  languageForPath,
  previewErrorFromMessage,
  previewUrl,
} from './app-projects';

describe('isAppProjectWriteTool', () => {
  it('matches every builder write tool, with or without a namespace', () => {
    for (const name of APP_PROJECT_WRITE_TOOLS) {
      expect(isAppProjectWriteTool(name)).toBe(true);
      expect(isAppProjectWriteTool(`Apps.${name}`)).toBe(true);
      expect(isAppProjectWriteTool(`Tool: ${name}`)).toBe(true);
    }
  });

  it('ignores read tools and other features', () => {
    expect(isAppProjectWriteTool('read_app_file')).toBe(false);
    expect(isAppProjectWriteTool('list_app_files')).toBe(false);
    expect(isAppProjectWriteTool('check_app')).toBe(false);
    expect(isAppProjectWriteTool('write_slides_deck')).toBe(false);
    expect(isAppProjectWriteTool('')).toBe(false);
    expect(isAppProjectWriteTool(null)).toBe(false);
  });
});

describe('buildFileTree', () => {
  it('nests folders first, then files, alphabetically', () => {
    const tree = buildFileTree([
      { path: 'index.html', size: 10 },
      { path: 'js/chart.js', size: 3 },
      { path: 'assets/img/logo.svg', size: 5 },
      { path: 'app.js', size: 1 },
      { path: 'js/app.js', size: 2 },
    ]);
    expect(tree.map((n) => n.name)).toEqual(['assets', 'js', 'app.js', 'index.html']);
    const js = tree.find((n) => n.name === 'js');
    expect(js?.children?.map((n) => n.path)).toEqual(['js/app.js', 'js/chart.js']);
    const img = tree[0].children?.[0];
    expect(img?.path).toBe('assets/img');
    expect(img?.children?.[0]).toMatchObject({ path: 'assets/img/logo.svg', size: 5 });
  });
});

describe('languageForPath', () => {
  it('maps static web files to Monaco languages', () => {
    expect(languageForPath('index.html')).toBe('html');
    expect(languageForPath('css/app.css')).toBe('css');
    expect(languageForPath('js/app.mjs')).toBe('javascript');
    expect(languageForPath('manifest.json')).toBe('json');
    expect(languageForPath('README.md')).toBe('markdown');
    expect(languageForPath('logo.svg')).toBe('xml');
    expect(languageForPath('Makefile')).toBe('plaintext');
  });
});

describe('preview helpers', () => {
  it('builds the preview URL on the API origin', () => {
    expect(previewUrl('https://api.example.com/', '/app-preview/tok/')).toBe(
      'https://api.example.com/app-preview/tok/',
    );
    expect(previewUrl('https://api.example.com', '/app-preview/tok/', 'pages/a b.html')).toBe(
      'https://api.example.com/app-preview/tok/pages/a%20b.html',
    );
  });

  it('reads only errors from the preview bridge', () => {
    expect(
      previewErrorFromMessage({ source: 'nexus-app-preview', type: 'error', message: 'boom' }),
    ).toBe('boom');
    expect(previewErrorFromMessage({ source: 'nexus-app-preview', type: 'load' })).toBeNull();
    expect(previewErrorFromMessage({ source: 'other', type: 'error', message: 'x' })).toBeNull();
    expect(previewErrorFromMessage('boom')).toBeNull();
  });

  it('links to the editor route', () => {
    expect(appEditorPath('ws 1', 'budget-tracker')).toBe(
      '/workspace/ws%201/apps/p/budget-tracker',
    );
  });
});
