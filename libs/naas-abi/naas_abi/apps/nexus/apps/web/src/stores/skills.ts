import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type SkillScope = 'user' | 'workspace' | 'organization';

export interface Skill {
  id: string;
  workspaceId: string; // Workspace the skill was created in
  organizationId: string | null;
  userId: string; // Creator
  name: string;
  slug: string; // Chat command: /<slug>
  description: string;
  prompt: string;
  scope: SkillScope;
  enabled: boolean;
  lastUsedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SkillCreateInput {
  name: string;
  prompt: string;
  slug?: string;
  description?: string;
  scope?: SkillScope;
  enabled?: boolean;
}

export interface SkillUpdateInput {
  name?: string;
  slug?: string;
  description?: string;
  prompt?: string;
  scope?: SkillScope;
  enabled?: boolean;
}

interface SkillsState {
  // Visible skills keyed by the workspace they were fetched FOR (an
  // organization-scoped skill created elsewhere is visible here too, so the
  // skill's own workspaceId cannot be used to reconstruct visibility).
  skillsByWorkspace: Record<string, Skill[]>;
  lastFetchedAt: Record<string, number>;
  fetchSkills: (workspaceId: string, force?: boolean) => Promise<void>;
  createSkill: (workspaceId: string, input: SkillCreateInput) => Promise<Skill>;
  updateSkill: (id: string, updates: SkillUpdateInput) => Promise<Skill>;
  deleteSkill: (id: string) => Promise<void>;
  markSkillUsed: (id: string) => Promise<void>;
  getWorkspaceSkills: (workspaceId: string | null) => Skill[];
  getSkillBySlug: (workspaceId: string | null, slug: string) => Skill | undefined;
}

const SKILLS_CACHE_TTL_MS = 5 * 60 * 1000;

const mapApiSkill = (s: any): Skill => ({
  id: s.id,
  workspaceId: s.workspace_id,
  organizationId: s.organization_id ?? null,
  userId: s.user_id,
  name: s.name,
  slug: s.slug,
  description: s.description ?? '',
  prompt: s.prompt,
  scope: s.scope === 'workspace' || s.scope === 'organization' ? s.scope : 'user',
  enabled: Boolean(s.enabled),
  lastUsedAt: s.last_used_at ?? null,
  createdAt: s.created_at,
  updatedAt: s.updated_at,
});

const apiHelpers = async () => {
  const { authFetch } = await import('./auth');
  const { getApiUrl } = await import('@/lib/config');
  return { authFetch, API_BASE: getApiUrl() };
};

const readDetail = async (response: Response, fallback: string): Promise<string> => {
  try {
    const body = await response.json();
    return body?.detail || fallback;
  } catch {
    return fallback;
  }
};

const mapAllWorkspaces = (
  byWorkspace: Record<string, Skill[]>,
  fn: (skills: Skill[]) => Skill[]
): Record<string, Skill[]> =>
  Object.fromEntries(Object.entries(byWorkspace).map(([ws, skills]) => [ws, fn(skills)]));

export const useSkillsStore = create<SkillsState>()(
  persist(
    (set, get) => ({
      skillsByWorkspace: {},
      lastFetchedAt: {},

      fetchSkills: async (workspaceId, force = false) => {
        if (!workspaceId) return;
        const last = get().lastFetchedAt[workspaceId] ?? 0;
        if (!force && Date.now() - last < SKILLS_CACHE_TTL_MS) return;

        try {
          const { authFetch, API_BASE } = await apiHelpers();
          const response = await authFetch(
            `${API_BASE}/api/skills/?workspace_id=${encodeURIComponent(workspaceId)}`
          );
          if (!response.ok) {
            console.error('Failed to fetch skills:', response.status);
            return;
          }
          const data = await response.json();
          const skills = Array.isArray(data) ? data.map(mapApiSkill) : [];
          set((state) => ({
            skillsByWorkspace: { ...state.skillsByWorkspace, [workspaceId]: skills },
            lastFetchedAt: { ...state.lastFetchedAt, [workspaceId]: Date.now() },
          }));
        } catch (error) {
          console.error('Failed to fetch skills:', error);
        }
      },

      createSkill: async (workspaceId, input) => {
        const { authFetch, API_BASE } = await apiHelpers();
        const response = await authFetch(`${API_BASE}/api/skills/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            name: input.name,
            slug: input.slug,
            description: input.description,
            prompt: input.prompt,
            scope: input.scope ?? 'user',
            enabled: input.enabled ?? true,
          }),
        });
        if (!response.ok) {
          throw new Error(await readDetail(response, 'Failed to create skill'));
        }
        const skill = mapApiSkill(await response.json());
        set((state) => ({
          skillsByWorkspace: {
            ...state.skillsByWorkspace,
            [workspaceId]: [skill, ...(state.skillsByWorkspace[workspaceId] ?? [])],
          },
        }));
        return skill;
      },

      updateSkill: async (id, updates) => {
        const { authFetch, API_BASE } = await apiHelpers();
        const response = await authFetch(`${API_BASE}/api/skills/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: updates.name,
            slug: updates.slug,
            description: updates.description,
            prompt: updates.prompt,
            scope: updates.scope,
            enabled: updates.enabled,
          }),
        });
        if (!response.ok) {
          throw new Error(await readDetail(response, 'Failed to update skill'));
        }
        const skill = mapApiSkill(await response.json());
        set((state) => ({
          skillsByWorkspace: mapAllWorkspaces(state.skillsByWorkspace, (skills) =>
            skills.map((s) => (s.id === id ? skill : s))
          ),
        }));
        return skill;
      },

      deleteSkill: async (id) => {
        const { authFetch, API_BASE } = await apiHelpers();
        const response = await authFetch(`${API_BASE}/api/skills/${id}`, {
          method: 'DELETE',
        });
        if (!response.ok && response.status !== 404) {
          throw new Error(await readDetail(response, 'Failed to delete skill'));
        }
        set((state) => ({
          skillsByWorkspace: mapAllWorkspaces(state.skillsByWorkspace, (skills) =>
            skills.filter((s) => s.id !== id)
          ),
        }));
      },

      markSkillUsed: async (id) => {
        // Optimistic local stamp so "latest used" ordering updates instantly.
        const now = new Date().toISOString();
        set((state) => ({
          skillsByWorkspace: mapAllWorkspaces(state.skillsByWorkspace, (skills) =>
            skills.map((s) => (s.id === id ? { ...s, lastUsedAt: now } : s))
          ),
        }));
        try {
          const { authFetch, API_BASE } = await apiHelpers();
          await authFetch(`${API_BASE}/api/skills/${id}/use`, { method: 'POST' });
        } catch (error) {
          console.error('Failed to mark skill used:', error);
        }
      },

      getWorkspaceSkills: (workspaceId) =>
        workspaceId ? (get().skillsByWorkspace[workspaceId] ?? []) : [],

      getSkillBySlug: (workspaceId, slug) =>
        get()
          .getWorkspaceSkills(workspaceId)
          .find((s) => s.slug === slug && s.enabled),
    }),
    {
      name: 'nexus-skills',
      partialize: (state) => ({
        skillsByWorkspace: state.skillsByWorkspace,
        lastFetchedAt: state.lastFetchedAt,
      }),
    }
  )
);
