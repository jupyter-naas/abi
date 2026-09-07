import { useWorkspaceStore } from '@/stores/workspace';

export function ontologyApiParams(
  extra: Record<string, string | null | undefined> = {},
): URLSearchParams {
  const params = new URLSearchParams();
  const workspaceId = useWorkspaceStore.getState().currentWorkspaceId;
  if (workspaceId) {
    params.set('workspace_id', workspaceId);
  }
  for (const [key, value] of Object.entries(extra)) {
    if (value) {
      params.set(key, value);
    }
  }
  return params;
}

export function ontologyApiQuery(
  extra: Record<string, string | null | undefined> = {},
): string {
  const encoded = ontologyApiParams(extra).toString();
  return encoded ? `?${encoded}` : '';
}
