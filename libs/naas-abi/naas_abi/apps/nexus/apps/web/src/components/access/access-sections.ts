import type { AccessView } from '@/lib/iam-admin/types';
import type { AccessLevel } from './access-scope';
import type { AccessPage } from './access-paths';

export type AccessSection = AccessPage;

/**
 * Each Access page opens with the action that lists what it shows, as `GET /access?scope=`
 * answers it (any of ``needs``); the API refuses the page's calls otherwise. Policies open to
 * whoever may create one too (they build it without the list), and to whoever may list the
 * attachments (they see the policies held here and who holds each: rights come from
 * policies). Nothing here depends on the level: the API answers the platform-only actions
 * (service accounts, approvals, the simulator, the audit) false at an org or a workspace.
 */
export const ACCESS_SECTIONS: { id: AccessSection; label: string; needs: string[] }[] = [
  { id: 'policies', label: 'Policies', needs: ['iam:ListPolicies', 'iam:CreatePolicy', 'iam:ListAttachments'] },
  { id: 'groups', label: 'Groups', needs: ['iam:ListGroups'] },
  { id: 'service-accounts', label: 'Service accounts', needs: ['iam:ListPrincipals'] },
  { id: 'approvals', label: 'Module approvals', needs: ['iam:ListManifests'] },
  { id: 'simulator', label: 'Simulator', needs: ['iam:Explain'] },
  { id: 'audit', label: 'Audit', needs: ['nexus:ReadSystem'] },
];

/** The pages of each level's Access: an organization and a workspace have Policies and Groups. */
export const LEVEL_SECTIONS: Record<AccessLevel, readonly AccessSection[]> = {
  platform: ACCESS_SECTIONS.map((s) => s.id),
  organization: ['policies', 'groups'],
  workspace: ['policies', 'groups'],
};

export function canDo(access: AccessView | null, action: string): boolean {
  return access?.actions[action] === true;
}

export function accessSection(id: AccessSection) {
  return ACCESS_SECTIONS.find((s) => s.id === id) ?? ACCESS_SECTIONS[0];
}

/** Whether ``access`` opens the page: any of its actions. */
export function opensSection(access: AccessView | null, id: AccessSection): boolean {
  return accessSection(id).needs.some((action) => canDo(access, action));
}

/** The pages of ``level`` the caller may open, in order. */
export function visibleSections(access: AccessView | null, level: AccessLevel = 'platform') {
  return ACCESS_SECTIONS.filter((s) => LEVEL_SECTIONS[level].includes(s.id) && opensSection(access, s.id));
}

/** Whether the caller would see a page of ``level``'s Access: the settings menus show the
 *  level's Access on exactly that, so the menu and the pages never disagree. */
export function opensAccess(access: AccessView | null, level: AccessLevel): boolean {
  return visibleSections(access, level).length > 0;
}
