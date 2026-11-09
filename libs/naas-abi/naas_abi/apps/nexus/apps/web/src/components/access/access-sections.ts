import type { AccessView } from '@/lib/iam-admin/types';

export type AccessSection =
  | 'people'
  | 'groups'
  | 'policies'
  | 'service-accounts'
  | 'approvals'
  | 'simulator'
  | 'audit';

/**
 * A section opens with the action that lists what it shows, as `GET /access?scope=` answers
 * it (any of ``needs``); the API refuses the section's calls otherwise. Policies open to whoever
 * may create one too: they build it without the list. Nothing here depends on the level: the
 * API answers the platform-only actions (service accounts, approvals, the simulator, the
 * audit) false at an org or a workspace.
 */
export const ACCESS_SECTIONS: { id: AccessSection; label: string; needs: string[] }[] = [
  { id: 'people', label: 'People & roles', needs: ['iam:ListAttachments'] },
  { id: 'groups', label: 'Groups', needs: ['iam:ListGroups'] },
  { id: 'policies', label: 'Policies', needs: ['iam:ListPolicies', 'iam:CreatePolicy'] },
  { id: 'service-accounts', label: 'Service accounts', needs: ['iam:ListPrincipals'] },
  { id: 'approvals', label: 'Module approvals', needs: ['iam:ListManifests'] },
  { id: 'simulator', label: 'Simulator', needs: ['iam:Explain'] },
  { id: 'audit', label: 'Audit', needs: ['nexus:ReadSystem'] },
];

export function canDo(access: AccessView | null, action: string): boolean {
  return access?.actions[action] === true;
}

/** The sections the caller may open, in order. */
export function visibleSections(access: AccessView | null) {
  return ACCESS_SECTIONS.filter((section) => section.needs.some((action) => canDo(access, action)));
}

export function parseAccessSection(
  value: string | null | undefined,
  access: AccessView | null,
): AccessSection | null {
  const visible = visibleSections(access);
  return visible.find((section) => section.id === value)?.id ?? visible[0]?.id ?? null;
}

/** Whether the page would show the caller a section: the settings menus show Roles &
 *  permissions on exactly that, so the menu and the page never disagree. */
export function opensRolesAndPermissions(access: AccessView | null): boolean {
  return visibleSections(access).length > 0;
}
