import type { MapsLayerGroupId } from './datasets';

export const WORKSPACE_LAYER_META_KEY = 'nexus-maps-workspace-layer-meta';
export const WORKSPACE_LAYER_META_UPDATED = 'nexus-maps-workspace-layer-meta-updated';

type WorkspaceMetaStore = Record<
  string,
  Record<string, { groupId: MapsLayerGroupId }>
>;

function readStore(): WorkspaceMetaStore {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(WORKSPACE_LAYER_META_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as WorkspaceMetaStore;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(store: WorkspaceMetaStore): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(WORKSPACE_LAYER_META_KEY, JSON.stringify(store));
  window.dispatchEvent(new CustomEvent(WORKSPACE_LAYER_META_UPDATED));
}

export function getWorkspaceLayerGroupId(
  workspaceId: string,
  layoutId: string,
): MapsLayerGroupId | undefined {
  return readStore()[workspaceId]?.[layoutId]?.groupId;
}

export function setWorkspaceLayerGroupId(
  workspaceId: string,
  layoutId: string,
  groupId: MapsLayerGroupId,
): void {
  const store = readStore();
  const workspace = store[workspaceId] ?? {};
  workspace[layoutId] = { groupId };
  store[workspaceId] = workspace;
  writeStore(store);
}

export function removeWorkspaceLayerMeta(workspaceId: string, layoutId: string): void {
  const store = readStore();
  const workspace = store[workspaceId];
  if (!workspace?.[layoutId]) return;
  delete workspace[layoutId];
  store[workspaceId] = workspace;
  writeStore(store);
}

export function subscribeWorkspaceLayerMeta(onChange: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const handler = () => onChange();
  window.addEventListener(WORKSPACE_LAYER_META_UPDATED, handler);
  return () => window.removeEventListener(WORKSPACE_LAYER_META_UPDATED, handler);
}
