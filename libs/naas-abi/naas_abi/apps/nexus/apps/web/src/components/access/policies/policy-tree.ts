/**
 * The policies of a scope as a tree: each sub-policy below its parent, the rest at the top. A
 * parent that is not in the list (it is owned above, or the caller may not see it) leaves its
 * sub-policies at the top, named as sub-policies of it.
 */
import type { PolicyView } from '@/lib/iam-admin/types';

export type TreeRow = { policy: PolicyView; depth: number };

const byName = (a: PolicyView, b: PolicyView) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });

/** The rows in tree order: a parent, then its sub-policies by name, depth first. */
export function policyTree(policies: PolicyView[]): TreeRow[] {
  const ids = new Set(policies.map((p) => p.id));
  const below = new Map<string, PolicyView[]>();
  const roots: PolicyView[] = [];
  for (const policy of policies) {
    const parent = policy.parent_id;
    if (parent && ids.has(parent) && parent !== policy.id) {
      below.set(parent, [...(below.get(parent) ?? []), policy]);
    } else {
      roots.push(policy);
    }
  }
  const rows: TreeRow[] = [];
  const seen = new Set<string>();
  const walk = (policy: PolicyView, depth: number) => {
    if (seen.has(policy.id)) return;
    seen.add(policy.id);
    rows.push({ policy, depth });
    for (const sub of [...(below.get(policy.id) ?? [])].sort(byName)) walk(sub, depth + 1);
  };
  // Managed policies (the roles) first, as listed; then the others by name.
  for (const root of [...roots.filter((p) => p.managed), ...roots.filter((p) => !p.managed).sort(byName)]) walk(root, 0);
  // A cycle IAM refuses to make, should one be read: still shown.
  for (const policy of policies) walk(policy, 0);
  return rows;
}
