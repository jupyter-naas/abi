import 'server-only';

import { mkdir, readdir, readFile, rename, unlink, writeFile } from 'fs/promises';
import { dirname, join } from 'path';

import type { EntityId, EntityManifest } from '@/lib/types';
import { fromR2ObjectKey, toR2ObjectKey } from '@/lib/server/dataKeys';

const DEMO_ENTITY_ID = '_demo';

// Single local source of truth: the bundled demo datastore shipped with this
// template (web/data). Mirrors the R2 bucket layout (keys are datastore-relative,
// e.g. `globals/entities.json`, `entities/<id>/manifest.json`). Override with
// DATA_LOCAL_ROOT to point at your own generated datastore.
const DEFAULT_DATASTORE_ROOT = 'data';

/**
 * Data source selector. Production (Cloudflare Workers) reads from R2 via the
 * bound bucket; everywhere else reads the local datastore directory. There is
 * exactly one path per environment — no cross-source fallback.
 */
function isProd(): boolean {
  return process.env.ENV === 'prod';
}

function getDatastoreRoot(): string {
  return process.env.DATA_LOCAL_ROOT ?? DEFAULT_DATASTORE_ROOT;
}

function normalizeKey(key: string): string {
  return key.replace(/^\/+/, '');
}

async function readLocalFile(relativeKey: string): Promise<string | null> {
  const fullPath = join(process.cwd(), getDatastoreRoot(), normalizeKey(relativeKey));
  try {
    return await readFile(fullPath, 'utf8');
  } catch {
    return null;
  }
}

async function readR2File(relativeKey: string): Promise<string | null> {
  try {
    const { getCloudflareContext } = await import('@opennextjs/cloudflare');
    const ctx = await getCloudflareContext({ async: true });
    const bucket = (ctx.env as { DATASETS?: R2Bucket }).DATASETS;
    if (!bucket) {
      return null;
    }
    const object = await bucket.get(toR2ObjectKey(relativeKey));
    if (!object) {
      return null;
    }
    return object.text();
  } catch {
    return null;
  }
}

async function writeLocalFile(relativeKey: string, content: string): Promise<boolean> {
  const fullPath = join(process.cwd(), getDatastoreRoot(), normalizeKey(relativeKey));
  // Write to a unique temp file then atomically rename over the target. rename(2)
  // is atomic on POSIX, so a concurrent read never sees a half-written file and
  // two concurrent writers can't interleave into a truncated-tail corruption —
  // each rename swaps in a complete document, last writer wins cleanly.
  const tmpPath = `${fullPath}.${process.pid}.${Date.now()}.${Math.random()
    .toString(36)
    .slice(2)}.tmp`;
  try {
    await mkdir(dirname(fullPath), { recursive: true });
    await writeFile(tmpPath, content, 'utf8');
    await rename(tmpPath, fullPath);
    return true;
  } catch {
    await unlink(tmpPath).catch(() => {});
    return false;
  }
}

async function writeR2File(relativeKey: string, content: string): Promise<boolean> {
  try {
    const { getCloudflareContext } = await import('@opennextjs/cloudflare');
    const ctx = await getCloudflareContext({ async: true });
    const bucket = (ctx.env as { DATASETS?: R2Bucket }).DATASETS;
    if (!bucket) {
      return false;
    }
    await bucket.put(toR2ObjectKey(relativeKey), content);
    return true;
  } catch {
    return false;
  }
}

async function listLocalFiles(relativePrefix: string): Promise<string[]> {
  const prefix = normalizeKey(relativePrefix).replace(/\/+$/, '');
  const dir = join(process.cwd(), getDatastoreRoot(), prefix);
  try {
    const entries = await readdir(dir, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isFile())
      .map((entry) => `${prefix}/${entry.name}`);
  } catch {
    return [];
  }
}

async function listR2Files(relativePrefix: string): Promise<string[]> {
  try {
    const { getCloudflareContext } = await import('@opennextjs/cloudflare');
    const ctx = await getCloudflareContext({ async: true });
    const bucket = (ctx.env as { DATASETS?: R2Bucket }).DATASETS;
    if (!bucket) {
      return [];
    }
    const prefix = `${toR2ObjectKey(normalizeKey(relativePrefix).replace(/\/+$/, ''))}/`;
    const keys: string[] = [];
    let cursor: string | undefined;
    do {
      const page = await bucket.list({ prefix, cursor });
      keys.push(...page.objects.map((object) => fromR2ObjectKey(object.key)));
      cursor = page.truncated ? page.cursor : undefined;
    } while (cursor);
    return keys;
  } catch {
    return [];
  }
}

export async function readDataFile(relativeKey: string): Promise<string | null> {
  return isProd() ? readR2File(relativeKey) : readLocalFile(relativeKey);
}

/** List datastore-relative keys of the files directly under a folder. */
export async function listDataFiles(relativePrefix: string): Promise<string[]> {
  return isProd() ? listR2Files(relativePrefix) : listLocalFiles(relativePrefix);
}

async function deleteLocalFile(relativeKey: string): Promise<boolean> {
  try {
    await unlink(join(process.cwd(), getDatastoreRoot(), normalizeKey(relativeKey)));
    return true;
  } catch {
    return false;
  }
}

async function deleteR2File(relativeKey: string): Promise<boolean> {
  try {
    const { getCloudflareContext } = await import('@opennextjs/cloudflare');
    const ctx = await getCloudflareContext({ async: true });
    const bucket = (ctx.env as { DATASETS?: R2Bucket }).DATASETS;
    if (!bucket) {
      return false;
    }
    await bucket.delete(toR2ObjectKey(relativeKey));
    return true;
  } catch {
    return false;
  }
}

export async function deleteDataFile(relativeKey: string): Promise<boolean> {
  return isProd() ? deleteR2File(relativeKey) : deleteLocalFile(relativeKey);
}

export async function writeDataFile(
  relativeKey: string,
  content: string,
): Promise<boolean> {
  return isProd() ? writeR2File(relativeKey, content) : writeLocalFile(relativeKey, content);
}

export async function writeJsonFile(
  relativeKey: string,
  value: unknown,
): Promise<boolean> {
  return writeDataFile(relativeKey, JSON.stringify(value, null, 2));
}

export async function readJsonFile<T>(relativeKey: string): Promise<T | null> {
  const raw = await readDataFile(relativeKey);
  if (!raw) {
    return null;
  }
  return JSON.parse(raw) as T;
}

export async function loadEntityManifest(
  entityId: EntityId,
): Promise<EntityManifest | null> {
  const primary = await readJsonFile<EntityManifest>(
    `entities/${entityId}/manifest.json`,
  );
  if (primary) {
    return primary;
  }
  return readJsonFile<EntityManifest>(`entities/${DEMO_ENTITY_ID}/manifest.json`);
}

interface R2Bucket {
  get(key: string): Promise<{ text(): Promise<string> } | null>;
  put(key: string, value: string): Promise<unknown>;
  list(options?: { prefix?: string; cursor?: string }): Promise<{
    objects: Array<{ key: string }>;
    truncated: boolean;
    cursor?: string;
  }>;
  delete(key: string): Promise<void>;
}
