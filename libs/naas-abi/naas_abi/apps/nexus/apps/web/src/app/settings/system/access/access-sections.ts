import type { AccessView } from '@/lib/iam-admin/types';

export type AccessSection =
  | 'policies'
  | 'attachments'
  | 'groups'
  | 'service-accounts'
  | 'approvals'
  | 'simulator'
  | 'audit';

/** A section opens with the action that lists what it shows; the API answers it with 403 otherwise. */
export const ACCESS_SECTIONS: { id: AccessSection; label: string; needs: string }[] = [
  { id: 'policies', label: 'Policies', needs: 'iam:ListPolicies' },
  { id: 'attachments', label: 'Attachments', needs: 'iam:ListAttachments' },
  { id: 'groups', label: 'Groups', needs: 'iam:ListGroups' },
  { id: 'service-accounts', label: 'Service accounts', needs: 'iam:ListPrincipals' },
  { id: 'approvals', label: 'Module approvals', needs: 'iam:ListManifests' },
  { id: 'simulator', label: 'Simulator', needs: 'iam:Explain' },
  { id: 'audit', label: 'Audit', needs: 'nexus:ReadSystem' },
];

export function canDo(access: AccessView | null, action: string): boolean {
  return access?.actions[action] === true;
}

/** The sections the caller may open, in order. */
export function visibleSections(access: AccessView | null) {
  return ACCESS_SECTIONS.filter((section) => canDo(access, section.needs));
}

export function parseAccessSection(
  value: string | null | undefined,
  access: AccessView | null,
): AccessSection | null {
  const visible = visibleSections(access);
  return visible.find((section) => section.id === value)?.id ?? visible[0]?.id ?? null;
}
