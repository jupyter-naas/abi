import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { findRepoRoot, resolveLocalImageFile } from './local-image-file';

describe('resolveLocalImageFile', () => {
  const root = mkdtempSync(path.join(tmpdir(), 'nexus-image-'));
  mkdirSync(path.join(root, 'src', 'mod'), { recursive: true });
  const rel = path.join('src', 'mod', 'portrait.png');
  const abs = path.join(root, rel);
  writeFileSync(abs, 'png');

  it('resolves repo-relative image paths', () => {
    assert.equal(resolveLocalImageFile('src/mod/portrait.png', root), abs);
  });

  it('resolves file URIs that sit under the repo', () => {
    assert.equal(resolveLocalImageFile(pathToFileURL(abs).href, root), abs);
  });

  it('rejects path escape and non-images', () => {
    assert.equal(resolveLocalImageFile('../secret.png', root), null);
    assert.equal(resolveLocalImageFile('src/mod/notes.txt', root), null);
    assert.equal(resolveLocalImageFile('file:///etc/hosts', root), null);
  });
});

describe('findRepoRoot', () => {
  it('skips a nested git checkout and uses the tree that has src/', () => {
    const outer = mkdtempSync(path.join(tmpdir(), 'nexus-repo-'));
    mkdirSync(path.join(outer, 'src'), { recursive: true });
    writeFileSync(path.join(outer, 'AGENTS.md'), 'root');
    writeFileSync(path.join(outer, '.git'), 'outer');
    const nested = path.join(outer, 'engine', 'apps', 'web');
    mkdirSync(nested, { recursive: true });
    writeFileSync(path.join(outer, 'engine', '.git'), 'nested');
    writeFileSync(path.join(outer, 'engine', 'AGENTS.md'), 'engine');
    assert.equal(findRepoRoot(nested), outer);
  });
});
