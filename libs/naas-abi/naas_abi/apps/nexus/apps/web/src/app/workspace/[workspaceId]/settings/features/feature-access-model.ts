/**
 * Settings › Features (`GET` / `PUT /api/workspaces/{id}/feature-access`): whether the workspace
 * offers each feature, as the API answers it, the changes a save sends, and the table's columns
 * (search, sort, filter, export, as Settings › Users). Pure: the view is `feature-access.tsx`. A feature is part of the workspace's offer, "<W> access" (S3, #1586):
 * Everyone puts it in, Nobody takes it out. Only… is gone: an exception for some people is a group
 * holding a policy. What may be changed is IAM's answer (`editable`, `reason`), never a role.
 */
import { ownerHref } from '@/components/access/policies/policy-owners';

export type FeatureChoice = 'everyone' | 'nobody';
export const FEATURE_CHOICES: { value: FeatureChoice; label: string; hint: string }[] = [
  { value: 'everyone', label: 'Everyone', hint: "Offered by the workspace: everyone in it, newcomers included." },
  {
    value: 'nobody',
    label: 'Nobody',
    hint: 'Not offered by the workspace: nobody in it uses it, admins included.',
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
  /** Always empty now (Only… is gone); kept as the API answers it. */
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

export type FeatureDraft = { choice: FeatureChoice };
export type FeatureChange = { feature: string; choice: FeatureChoice };

export function draftOf(row: FeatureRow): FeatureDraft {
  return { choice: row.choice };
}

/** The rows by name, A to Z. */
export function sortedRows(rows: FeatureRow[]): FeatureRow[] {
  return [...rows].sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
}

/** What a save sends: each row whose draft is not what it holds. */
export function changesFrom(rows: FeatureRow[], drafts: Record<string, FeatureDraft>): FeatureChange[] {
  return rows.flatMap((row) => {
    const draft = drafts[row.key];
    if (!draft || draft.choice === row.choice) return [];
    return [{ feature: row.key, choice: draft.choice }];
  });
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

/** The columns of the features table: each sorts and filters, as Settings › Users. */
export type FeatureColumnId = 'feature' | 'offered' | 'policies';
export const FEATURE_COLUMNS: { id: FeatureColumnId; label: string }[] = [
  { id: 'feature', label: 'Feature' },
  { id: 'offered', label: 'Offered to' },
  { id: 'policies', label: 'Other policies' },
];

const CHOICE_LABELS: Record<FeatureChoice, string> = { everyone: 'Everyone', nobody: 'Nobody' };

/** What a column filter sees of a row (what it holds, not an unsaved draft: a row never leaves
 *  the table while it is being changed). */
export function featureCellValues(row: FeatureRow, column: FeatureColumnId): string[] {
  if (column === 'feature') return [row.label];
  if (column === 'offered') return [CHOICE_LABELS[row.choice]];
  return row.also.length === 0 ? ['None'] : otherPolicies(row).map(({ policy }) => policy.name);
}

/** What the search bar reads of a row: its name and key, who it is offered to, the other
 *  policies, and whether it is not offered here or was changed on its policy's page. */
export function featureSearchTexts(row: FeatureRow): string[] {
  return [
    row.label,
    row.key,
    CHOICE_LABELS[row.choice],
    ...row.also.map((policy) => `${policy.name} ${policy.effect === 'Deny' ? 'denied' : 'granted'}`),
    row.offered ? '' : 'not offered',
    row.hand_edited ? 'changed by hand' : '',
  ];
}

export const FEATURE_EXPORT_HEADERS = ['Feature', 'Key', 'Offered to', 'Offered here', 'Other policies'];

/** A row of the CSV / Excel export, as the table shows it saved. */
export function featureExportRow(row: FeatureRow): string[] {
  return [
    row.label,
    row.key,
    CHOICE_LABELS[row.choice],
    row.offered ? 'Yes' : 'No',
    otherPolicies(row)
      .map(({ text }) => text)
      .join('; '),
  ];
}
