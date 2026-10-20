/**
 * Sidebar layer groups. A group is a label on a feed (`group` on the layer
 * record, built-in dataset or imported layer), not a record of its own: the
 * sidebar groups feeds sharing a label (case-insensitive).
 */

export const DEFAULT_LAYER_GROUP = 'Custom';
/** Mirrors the API's MAX_GROUP_LENGTH. */
export const MAX_LAYER_GROUP_LENGTH = 80;

/** Labels for the slugs records carried as `category` before `group` (mirrors the API). */
const LEGACY_GROUP_LABELS: Readonly<Record<string, string>> = {
  public: 'Public',
  environment: 'Environment',
  sigint: 'SIGINT',
  situation: 'Situation',
  'organizations-facility': 'Organizations Facilities',
  custom: DEFAULT_LAYER_GROUP,
};

export function legacyGroupLabel(category: string | null | undefined): string {
  const slug = (category ?? '').trim();
  return LEGACY_GROUP_LABELS[slug.toLowerCase()] ?? (slug || DEFAULT_LAYER_GROUP);
}

/** A record's group: `group`, else its legacy `category`, else Custom. */
export function layoutGroup(record: { group?: string | null; category?: string | null }): string {
  return record.group?.trim() || legacyGroupLabel(record.category);
}

export function layerGroupKey(label: string): string {
  return label.trim().toLowerCase();
}

/** Distinct group labels (first spelling wins), sorted by label with Custom last. */
export function layerGroupLabels(groups: Iterable<string>): string[] {
  const byKey = new Map<string, string>();
  for (const raw of groups) {
    const label = raw.trim();
    if (label && !byKey.has(layerGroupKey(label))) byKey.set(layerGroupKey(label), label);
  }
  const customKey = layerGroupKey(DEFAULT_LAYER_GROUP);
  return [...byKey.entries()]
    .sort(([a, labelA], [b, labelB]) =>
      a === customKey ? 1 : b === customKey ? -1 : labelA.localeCompare(labelB, undefined, { sensitivity: 'base' }),
    )
    .map(([, label]) => label);
}

const LEGACY_GROUPS_KEY = 'nexus-maps-custom-layer-groups';
const LEGACY_LAYER_META_KEY = 'nexus-maps-workspace-layer-meta';

type LegacyStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function readJson(storage: LegacyStorage, key: string): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(storage.getItem(key) ?? '{}');
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function writeWithout(storage: LegacyStorage, key: string, store: Record<string, unknown>, workspaceId: string) {
  delete store[workspaceId];
  if (Object.keys(store).length) storage.setItem(key, JSON.stringify(store));
  else storage.removeItem(key);
}

export interface LegacyLocalGroups {
  /** Layer id → group label, for feeds whose group was kept in this browser. */
  layers: Record<string, string>;
  /** Browser-only group id → label (imported layers stored the id). */
  labels: Record<string, string>;
}

/**
 * Group choices older versions kept in this browser, removed from storage as
 * they are read. The caller writes them on the records.
 */
export function takeLegacyLocalGroups(
  workspaceId: string,
  storage: LegacyStorage | undefined = typeof window === 'undefined' ? undefined : window.localStorage,
): LegacyLocalGroups {
  if (!storage) return { layers: {}, labels: {} };
  const groups = readJson(storage, LEGACY_GROUPS_KEY);
  const meta = readJson(storage, LEGACY_LAYER_META_KEY);
  const labels = new Map<string, string>();
  const ownGroups = groups[workspaceId];
  if (Array.isArray(ownGroups)) {
    for (const group of ownGroups) {
      if (group && typeof group.id === 'string' && typeof group.label === 'string') {
        labels.set(group.id, group.label);
      }
    }
  }
  const out: Record<string, string> = {};
  const ownMeta = meta[workspaceId];
  if (ownMeta && typeof ownMeta === 'object') {
    for (const [layerId, value] of Object.entries(ownMeta as Record<string, unknown>)) {
      const groupId = (value as { groupId?: unknown } | null)?.groupId;
      if (typeof groupId === 'string' && groupId) {
        out[layerId] = labels.get(groupId) ?? legacyGroupLabel(groupId);
      }
    }
  }
  if (workspaceId in groups) writeWithout(storage, LEGACY_GROUPS_KEY, groups, workspaceId);
  if (workspaceId in meta) writeWithout(storage, LEGACY_LAYER_META_KEY, meta, workspaceId);
  return { layers: out, labels: Object.fromEntries(labels) };
}
