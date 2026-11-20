/**
 * The body of `POST /api/workspaces` from Organization settings › Workspaces › Create (S2, #1585):
 * a workspace is created with its workspace admin, `admin_id`, who defaults to the creator and
 * joins "<W> admins" and "<W> workspace". No Owner is picked: nothing assigns it any more.
 */
/** The catalog seed as the create page builds it (`catalogSeedPayload`): passed through. */
export type CatalogSeedPayload = Record<string, unknown> | null;

export type WorkspaceCreateDraft = {
  name: string;
  slug: string;
  organizationId: string;
  /** The person picked as the workspace admin; empty: the creator. */
  adminId: string;
  creatorId?: string | null;
  group?: string;
  description?: string;
  primaryColor: string;
  accentColor?: string;
  catalogSeed?: CatalogSeedPayload;
};

export function workspaceCreateBody(draft: WorkspaceCreateDraft): Record<string, unknown> {
  return {
    name: draft.name.trim(),
    slug: draft.slug,
    organization_id: draft.organizationId,
    admin_id: draft.adminId || draft.creatorId || undefined,
    workspace_group: draft.group?.trim() || null,
    description: draft.description?.trim() || null,
    primary_color: draft.primaryColor,
    accent_color: draft.accentColor || null,
    catalog_seed: draft.catalogSeed,
  };
}

/** The refusals of the create route that are about the workspace admin picked (400: not a
 *  person of the organization's directory, not a known user): shown at the picker. */
export function adminRefusal(status: number, detail: string): string | null {
  if (status !== 400) return null;
  return /workspace admin/i.test(detail) ? detail : null;
}
