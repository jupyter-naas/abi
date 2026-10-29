import type { PrincipalView } from '@/lib/iam-admin/types';
import { parseScope, type ContainerStep } from '../access-scope';

/** What a person calls a principal: their name, else email, else the id. */
export function principalLabel(principal: Pick<PrincipalView, 'id' | 'display_name' | 'email' | 'name'> | null, fallback: string): string {
  if (!principal) return fallback;
  return principal.display_name || principal.email || principal.name || principal.id;
}

/** A container step in words: `Organization acme`, `Workspace ws-1`, else `<type> <id>`. */
function stepLabel(step: ContainerStep): string {
  if (step.service === 'nexus' && step.type === 'organization') return `Organization ${step.id}`;
  if (step.service === 'nexus' && step.type === 'workspace') return `Workspace ${step.id}`;
  return `${step.type} ${step.id}`;
}

/** A scope in words: the platform (`abi:`), a container (`abi:nexus:organization/<org>`, its
 *  workspace `.../nexus:workspace/<ws>`), below one (`<container>/*`), or null for everywhere. */
export function scopeLabel(scope: string | null): string {
  if (scope === null) return 'Everywhere';
  const parsed = parseScope(scope);
  if (!parsed) return scope;
  const { containers, below } = parsed;
  if (containers.length === 0) return 'Platform';
  const last = containers[containers.length - 1];
  const parent = containers[containers.length - 2];
  const named = parent ? `${stepLabel(last)} of ${parent.id}` : stepLabel(last);
  if (!below) return named;
  return last.service === 'nexus' && last.type === 'organization'
    ? `${named} and its workspaces`
    : `${named} and everything in it`;
}
