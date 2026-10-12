import { MAPS_CATEGORIES, type MapsDatasetCategory, type MapsLayerGroupId } from './datasets';

export const CUSTOM_LAYER_GROUPS_KEY = 'nexus-maps-custom-layer-groups';
export const CUSTOM_LAYER_GROUPS_UPDATED = 'nexus-maps-custom-layer-groups-updated';

export type CustomLayerGroup = {
  id: `user-${string}`;
  label: string;
};

const USER_GROUP_ID = /^user-[a-z0-9][a-z0-9-]{0,46}$/;

type WorkspaceGroupStore = Record<string, CustomLayerGroup[]>;

function readStore(): WorkspaceGroupStore {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(CUSTOM_LAYER_GROUPS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as WorkspaceGroupStore;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(store: WorkspaceGroupStore): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(CUSTOM_LAYER_GROUPS_KEY, JSON.stringify(store));
  window.dispatchEvent(new CustomEvent(CUSTOM_LAYER_GROUPS_UPDATED));
}

export function loadCustomLayerGroups(workspaceId: string): CustomLayerGroup[] {
  return readStore()[workspaceId] ?? [];
}

export function slugifyLayerGroupId(label: string): `user-${string}` {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 46);
  const core = slug || 'group';
  const id = `user-${core}` as `user-${string}`;
  return USER_GROUP_ID.test(id) ? id : (`user-${core.slice(0, 40)}` as `user-${string}`);
}

export function validateCustomGroupLabel(label: string): string | null {
  if (!label.trim()) return 'Group name is required.';
  const id = slugifyLayerGroupId(label);
  if (!USER_GROUP_ID.test(id)) return 'Choose a shorter group name.';
  return null;
}

export function saveCustomLayerGroup(workspaceId: string, label: string): CustomLayerGroup {
  const id = slugifyLayerGroupId(label);
  const group: CustomLayerGroup = { id, label: label.trim() };
  const store = readStore();
  const list = store[workspaceId] ?? [];
  const index = list.findIndex((item) => item.id === id);
  if (index >= 0) list[index] = group;
  else list.push(group);
  store[workspaceId] = list.sort((a, b) => a.label.localeCompare(b.label));
  writeStore(store);
  return group;
}

export function subscribeCustomLayerGroups(onChange: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const handler = () => onChange();
  window.addEventListener(CUSTOM_LAYER_GROUPS_UPDATED, handler);
  return () => window.removeEventListener(CUSTOM_LAYER_GROUPS_UPDATED, handler);
}

export const BUILTIN_LAYER_GROUPS = MAPS_CATEGORIES;

export function isBuiltinLayerGroup(id: string): id is MapsDatasetCategory {
  return BUILTIN_LAYER_GROUPS.some((group) => group.id === id);
}

export function layerGroupLabel(
  groupId: string,
  customGroups: ReadonlyArray<CustomLayerGroup>,
): string {
  const builtin = BUILTIN_LAYER_GROUPS.find((group) => group.id === groupId);
  if (builtin) return builtin.label;
  return customGroups.find((group) => group.id === groupId)?.label ?? groupId;
}

export function layerGroupDefinitions(
  customGroups: ReadonlyArray<CustomLayerGroup> = [],
): Array<{ id: string; label: string }> {
  return [
    ...BUILTIN_LAYER_GROUPS.map(({ id, label }) => ({ id, label })),
    ...customGroups.map(({ id, label }) => ({ id, label })),
  ];
}

export const CREATE_LAYER_GROUP_VALUE = '__create_group__';

export function resolveLayerGroupSelection(
  workspaceId: string,
  groupSelection: string,
  newGroupName: string,
): { groupId?: MapsLayerGroupId; error?: string } {
  if (groupSelection === CREATE_LAYER_GROUP_VALUE) {
    const groupError = validateCustomGroupLabel(newGroupName);
    if (groupError) return { error: groupError };
    return { groupId: saveCustomLayerGroup(workspaceId, newGroupName).id };
  }
  return { groupId: groupSelection as MapsLayerGroupId };
}
