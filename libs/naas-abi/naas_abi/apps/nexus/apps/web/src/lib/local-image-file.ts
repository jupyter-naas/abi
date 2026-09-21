import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const IMAGE_EXT = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.avif', '.bmp', '.ico']);

const MIME: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.avif': 'image/avif',
  '.bmp': 'image/bmp',
  '.ico': 'image/x-icon',
};

/**
 * Walk up from the web app. Nested checkouts (engine submodule) have .git first;
 * prefer the outermost tree that actually contains src/ so module portraits resolve.
 */
export function findRepoRoot(start = process.cwd()): string | null {
  const candidates: string[] = [];
  let dir = path.resolve(start);
  for (let i = 0; i < 16; i++) {
    const hasGit = existsSync(path.join(dir, '.git'));
    const hasSrcHandbook = existsSync(path.join(dir, 'src')) && existsSync(path.join(dir, 'AGENTS.md'));
    if (hasGit || hasSrcHandbook) candidates.push(dir);
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  for (let i = candidates.length - 1; i >= 0; i--) {
    if (existsSync(path.join(candidates[i], 'src'))) return candidates[i];
  }
  return candidates[0] || process.env.ABI_REPO_ROOT?.trim() || null;
}

function underRoot(resolved: string, repoRoot: string): boolean {
  const root = path.resolve(repoRoot);
  const prefix = root.endsWith(path.sep) ? root : root + path.sep;
  return resolved === root || resolved.startsWith(prefix);
}

/**
 * Resolve a file:// URI or repo-relative image path to a file under the repo.
 * Rejects absolute paths outside the repo and non-image suffixes.
 */
export function resolveLocalImageFile(url: string, repoRoot = findRepoRoot()): string | null {
  const trimmed = url.trim();
  if (!trimmed || !repoRoot) return null;

  let candidate: string | null = null;
  if (trimmed.startsWith('file://')) {
    try {
      candidate = fileURLToPath(trimmed);
    } catch {
      return null;
    }
  } else if (!trimmed.includes('://') && !path.isAbsolute(trimmed)) {
    const rel = trimmed.replace(/^\/+/, '');
    if (!rel || rel.split(/[\\/]/).includes('..')) return null;
    candidate = path.join(repoRoot, rel);
  } else {
    return null;
  }

  const resolved = path.resolve(candidate);
  if (!underRoot(resolved, repoRoot)) return null;
  if (!IMAGE_EXT.has(path.extname(resolved).toLowerCase())) return null;
  if (!existsSync(resolved)) return null;
  return resolved;
}

export function readLocalImage(url: string): { bytes: Buffer; contentType: string } | null {
  const file = resolveLocalImageFile(url);
  if (!file) return null;
  return {
    bytes: readFileSync(file),
    contentType: MIME[path.extname(file).toLowerCase()] || 'application/octet-stream',
  };
}
