import { create } from 'zustand';
import { isAppProjectWriteTool } from '@/lib/app-projects';

export { isAppProjectWriteTool };

/** Fired when the Apps agent changed a project (chat tool result). */
export const APP_PROJECT_UPDATED_EVENT = 'app-project-updated';

export type AppProjectUpdatedDetail = {
  slug?: string;
  source?: string;
};

export function dispatchAppProjectUpdated(detail: AppProjectUpdatedDetail = {}) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<AppProjectUpdatedDetail>(APP_PROJECT_UPDATED_EVENT, { detail }),
  );
}

interface AppProjectsState {
  /** True between an agent write tool call and its result (editor banner). */
  agentWriting: boolean;
  setAgentWriting: (writing: boolean) => void;
}

export const useAppProjectsStore = create<AppProjectsState>((set) => ({
  agentWriting: false,
  setAgentWriting: (writing) => set({ agentWriting: writing }),
}));

/** Chat stream hook: a builder tool started. */
export function noteAppProjectToolStart(rawTool: string): void {
  if (isAppProjectWriteTool(rawTool)) useAppProjectsStore.getState().setAgentWriting(true);
}

/** Chat stream hook: a builder tool returned; refresh the editor on success. */
export function noteAppProjectToolResult(rawTool: string, output: string): void {
  if (!isAppProjectWriteTool(rawTool)) return;
  useAppProjectsStore.getState().setAgentWriting(false);
  let slug: string | undefined;
  try {
    const parsed = JSON.parse(output) as { slug?: unknown; error?: unknown };
    if (parsed && parsed.error) return;
    if (typeof parsed?.slug === 'string') slug = parsed.slug;
  } catch {
    /* plain-text tool output */
  }
  dispatchAppProjectUpdated({ slug, source: rawTool });
}
