/**
 * General › Features (`GET` / `PUT /api/workspaces/{id}/feature-access`): who may use each feature
 * of the workspace, as the API answers it, and the changes a save sends. Pure: the view is
 * `feature-access.tsx`. Each choice is a policy the API writes as the caller (`Feature · <name>`);
 * what may be changed is IAM's answer (`editable`, `reason`), never a role.
 */
import { ownerHref } from '@/components/access/policies/policy-owners';

export type FeatureChoice = 'everyone' | 'only' | 'nobody';
export const FEATURE_CHOICES: { value: FeatureChoice; label: string; hint: string }[] = [
  { value: 'everyone', label: 'Everyone', hint: "The workspace's members, newcomers included." },
  { value: 'only', label: 'Only…', hint: 'The members and groups you choose.' },
  {
    value: 'nobody',
    label: 'Nobody',
    hint: 'Its policy attached to no one here. Platform administrators still see every feature.',
  },
];

export type PrincipalRef = { id: string; kind: string; name: string };
export type PolicyRef = { id: string; name: string; owner_scope: string };
/** Another policy naming the feature here: it grants or denies it beside the choice. */
export type OtherPolicy = PolicyRef & { effect: 'Allow' | 'Deny'; attached: boolean };

export type FeatureRow = {
  key: string;
  label: string;
  choice: FeatureChoice;
  /** Only…: who holds the feature's policy at the workspace. */
  principals: PrincipalRef[];
  /** The feature's policy, once a save made it. */
  policy: PolicyRef | null;
  /** Its policy was changed on its page: shown, never rewritten from here. */
  hand_edited: boolean;
  /** Whether the workspace's access policy (and those above it) allow the feature. */
  offered: boolean;
  /** Whether the caller holds the feature here (what they may grant). */
  held: boolean;
  editable: boolean;
  reason: string | null;
  also: OtherPolicy[];
};

export type FeatureAccessState = {
  workspace_id: string;
  scope: string;
  access_policy: PolicyRef | null;
  members_group: PrincipalRef | null;
  can: { create: boolean; attach: boolean; detach: boolean; widen: boolean };
  features: FeatureRow[];
  /** After a save: the features IAM (or the row's rules) refused, with why. */
  errors?: Record<string, string>;
};

export type FeatureDraft = { choice: FeatureChoice; principals: string[] };
export type FeatureChange = { feature: string; choice: FeatureChoice; principals?: string[] };

export function draftOf(row: FeatureRow): FeatureDraft {
  return { choice: row.choice, principals: row.principals.map((p) => p.id) };
}

function sameDraft(a: FeatureDraft, b: FeatureDraft): boolean {
  if (a.choice !== b.choice) return false;
  if (a.choice !== 'only') return true;
  const left = [...a.principals].sort();
  const right = [...b.principals].sort();
  return left.length === right.length && left.every((id, i) => id === right[i]);
}

/** The rows by name, A to Z. */
export function sortedRows(rows: FeatureRow[]): FeatureRow[] {
  return [...rows].sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
}

/** What a save sends: each row whose draft is not what it holds. */
export function changesFrom(rows: FeatureRow[], drafts: Record<string, FeatureDraft>): FeatureChange[] {
  return rows.flatMap((row) => {
    const draft = drafts[row.key];
    if (!draft || sameDraft(draft, draftOf(row))) return [];
    return [
      draft.choice === 'only'
        ? { feature: row.key, choice: draft.choice, principals: draft.principals }
        : { feature: row.key, choice: draft.choice },
    ];
  });
}

/** Why a draft cannot be saved (Only… with nobody chosen), else null. */
export function draftProblem(row: FeatureRow, draft: FeatureDraft | undefined): string | null {
  if (draft?.choice === 'only' && draft.principals.length === 0) {
    return `Choose who may use ${row.label}.`;
  }
  return null;
}

/** Each choice of a row and whether it can be picked: an editable row; a feature the workspace
 *  does not offer can only be taken back (Nobody). */
export function choicesOf(
  row: FeatureRow,
): { value: FeatureChoice; label: string; hint: string; enabled: boolean }[] {
  return FEATURE_CHOICES.map((choice) => ({
    ...choice,
    enabled: row.editable && (row.offered || choice.value === 'nobody'),
  }));
}

export type RowNote = { tone: 'info' | 'warning'; text: string; href?: string | null; link?: string };

/** What a row says beside its choice: the ceiling, a policy changed by hand, why it is
 *  read-only. */
export function rowNotes(row: FeatureRow, state: Pick<FeatureAccessState, 'access_policy' | 'can'>): RowNote[] {
  const notes: RowNote[] = [];
  if (!row.offered) {
    const access = state.access_policy;
    const widen = access && state.can.widen ? ownerHref(access.owner_scope, access.id) : null;
    notes.push({
      tone: 'warning',
      text: access
        ? `Not offered in this workspace: ${access.name} does not allow it.`
        : 'Not offered in this workspace.',
      ...(access && widen ? { href: widen, link: `Widen ${access.name}` } : {}),
    });
  }
  if (row.hand_edited && row.policy) {
    notes.push({
      tone: 'info',
      text: `${row.policy.name} was changed on its policy page: read-only here.`,
      href: ownerHref(row.policy.owner_scope, row.policy.id),
      link: 'Open it',
    });
  } else if (!row.editable && row.reason && (row.offered || row.held)) {
    notes.push({ tone: 'info', text: row.reason });
  }
  return notes;
}

/** The other policies naming a feature, as a row lists them: what each does, Deny first. */
export function otherPolicies(row: FeatureRow): { policy: OtherPolicy; text: string; href: string | null }[] {
  return [...row.also]
    .sort((a, b) => (a.effect === b.effect ? a.name.localeCompare(b.name) : a.effect === 'Deny' ? -1 : 1))
    .map((policy) => ({
      policy,
      text: `${policy.effect === 'Deny' ? 'Also denied by' : 'Also granted by'} ${policy.name}${
        policy.attached ? '' : ' (attached nowhere)'
      }`,
      href: ownerHref(policy.owner_scope, policy.id),
    }));
}

/** The members and groups Only… may name, minus those chosen: people first, by name. */
export function offeredPrincipals(candidates: PrincipalRef[], chosen: string[]): PrincipalRef[] {
  const taken = new Set(chosen);
  return candidates
    .filter((p) => !taken.has(p.id))
    .sort((a, b) => (a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind === 'user' ? -1 : 1));
}
