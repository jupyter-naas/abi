import type { PrincipalView } from '@/lib/iam-admin/types';

/** What a person calls a principal: their name, else email, else the id. */
export function principalLabel(principal: Pick<PrincipalView, 'id' | 'display_name' | 'email' | 'name'> | null, fallback: string): string {
  if (!principal) return fallback;
  return principal.display_name || principal.email || principal.name || principal.id;
}

/** A scope in words: `abi:<org>:<workspace>` (`-`: the org itself), or null for everywhere. */
export function scopeLabel(scope: string | null): string {
  if (scope === null) return 'Everywhere';
  const [prefix, org, workspace] = scope.split(':');
  if (prefix !== 'abi' || org === undefined || workspace === undefined) return scope;
  if (org === '-' && workspace === '-') return 'Platform';
  if (workspace === '-') return `Organization ${org}`;
  if (workspace === '*') return `Every workspace of ${org}`;
  return `Workspace ${workspace} of ${org}`;
}
