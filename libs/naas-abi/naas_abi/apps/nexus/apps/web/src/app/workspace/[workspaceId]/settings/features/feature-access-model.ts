/**
 * Settings › Features (`GET` / `PUT /api/workspaces/{id}/feature-access`): whether the workspace
 * offers each feature, as the API answers it, the changes a save sends, and the table's columns
 * (search, sort, filter, export, as Settings › Users). Pure: the view is `feature-access.tsx`. A feature is part of the workspace's offer, "<W> access" (S3, #1586):
 * Everyone puts it in, Nobody takes it out. Only… is gone: an exception for some people is a group
 * holding a policy. What may be changed is IAM's answer (`editable`, `reason`), never a role.
 *
 * The table has one Access column (None, Read, Write, Admin): None takes the feature out (Nobody)
 * and caps it at None, any other level puts it in (Everyone) at that level (`levelPlan`). A
 * feature taken out shows None whatever level is stored (`shownLevel`).
 */
import { ownerHref } from '@/components/access/policies/policy-owners';
import { LEVEL_LABELS, type AccessLevel } from '@/lib/access-model/access-levels';

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
  /** The policy edited: "<W> access" (the workspace's offer) by default, or another policy of
   *  the workspace (what it grants its holders, within the offer). */
  policy?: PolicyRef | null;
  /** The policies that may be edited ("<W> access" first). */
  policies?: PolicyRef[];
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

/** The choices of another policy than "<W> access": what it grants whoever holds it. */
export const GRANT_CHOICES: { value: FeatureChoice; label: string; hint: string }[] = [
  { value: 'everyone', label: 'Granted', hint: 'Whoever holds this policy uses it here, within the workspace’s offer.' },
  { value: 'nobody', label: 'Not granted', hint: 'This policy does not grant it.' },
];

/** Whether the state is "<W> access", the workspace's offer (not another policy of it). */
export function editsOffer(state: Pick<FeatureAccessState, 'policy' | 'access_policy'> | null): boolean {
  return !state?.policy || !state.access_policy || state.policy.id === state.access_policy.id;
}

/** Each choice of a row and whether it can be picked: an editable row; a feature the ceiling
 *  does not offer can only be taken back (Nobody). Another policy than the offer says Granted. */
export function choicesOf(
  row: FeatureRow,
  offer = true,
): { value: FeatureChoice; label: string; hint: string; enabled: boolean }[] {
  return (offer ? FEATURE_CHOICES : GRANT_CHOICES).map((choice) => ({
    ...choice,
    enabled: row.editable && (row.offered || choice.value === 'nobody'),
  }));
}

/** The level a row shows: None for a feature taken out (Nobody), whatever level is stored, since
 *  nobody uses it; otherwise its level (null while the levels are not read). */
export function shownLevel(choice: FeatureChoice, level: AccessLevel | null): AccessLevel | null {
  return choice === 'nobody' ? 'none' : level;
}

/** The levels a row may be set to: every one it has while it may be offered (`choicesOf`), only
 *  None for a feature the ceiling does not offer, none for a read-only row. */
export function pickableLevels(row: FeatureRow, levels: AccessLevel[], offer = true): AccessLevel[] {
  const can = (value: FeatureChoice) => choicesOf(row, offer).find((c) => c.value === value)?.enabled ?? false;
  return levels.filter((level) => can(level === 'none' ? 'nobody' : 'everyone'));
}

/** What a save sends for the levels picked (`drafts`, by feature): each feature whose choice the
 *  pick changes (None → Nobody, any other level → Everyone), and each level that changes
 *  (`saved`, the level stored), None included: taken out, a feature is capped at None too. */
export function levelPlan(
  rows: FeatureRow[],
  drafts: Record<string, AccessLevel>,
  saved: (key: string) => AccessLevel | null,
): { features: FeatureChange[]; levels: Record<string, AccessLevel> } {
  const features: FeatureChange[] = [];
  const levels: Record<string, AccessLevel> = {};
  for (const row of rows) {
    const level = drafts[row.key];
    if (!level) continue;
    const choice: FeatureChoice = level === 'none' ? 'nobody' : 'everyone';
    if (choice !== row.choice) features.push({ feature: row.key, choice });
    if (level !== saved(row.key)) levels[`feature:${row.key}`] = level;
  }
  return { features, levels };
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

/** What each Nexus feature is, as its row says it. */
export const FEATURE_DESCRIPTIONS: Record<string, string> = {
  agents: 'The agents people chat with and build here.',
  apps: 'The apps opened in the workspace (embedded pages and tools).',
  chat: 'Conversations with the agents.',
  code: 'The code workspace.',
  datasets: 'The datasets read and queried here.',
  documents: 'Documents written and edited here.',
  files: 'The workspace’s own files (Workspace Files), and My Files.',
  graph: 'The knowledge graph: its views and graph explorer.',
  maps: 'Maps, their feeds and layers.',
  marketplace: 'The modules people browse and add.',
  ontology: 'The ontologies and their entities.',
  search: 'The search across the workspace and the web.',
  settings: 'The workspace settings pages.',
  sheets: 'Spreadsheets.',
  skills: 'Saved prompts run as commands.',
  slides: 'Slide decks.',
  tasks: 'Tasks and their runs.',
};

export function featureDescription(key: string): string {
  return FEATURE_DESCRIPTIONS[key] ?? '';
}

/** The settings page each feature is configured on, under the workspace (`/settings/...`). */
export const FEATURE_PAGES: Record<string, string> = {
  agents: '/settings/agents',
  apps: '/settings/apps',
  chat: '/settings/models',
  files: '/settings/files',
  graph: '/settings/graphs',
  maps: '/settings/maps',
  marketplace: '/settings/modules',
  ontology: '/settings/ontologies',
  search: '/settings/search',
  skills: '/settings/skills',
};

export function featurePage(workspaceId: string, key: string): string | null {
  const path = FEATURE_PAGES[key];
  return path ? `/workspace/${workspaceId}${path}` : null;
}

/** The columns of the features table: each sorts and filters, as Settings › Users. */
export type FeatureColumnId = 'feature' | 'description' | 'access';
export const FEATURE_COLUMNS: { id: FeatureColumnId; label: string }[] = [
  { id: 'feature', label: 'Feature' },
  { id: 'description', label: 'Description' },
  // How far people go with it (`access-levels`): the page fills its values.
  { id: 'access', label: 'Access' },
];

/** What a column filter sees of a row (what it holds, not an unsaved draft: a row never leaves
 *  the table while it is being changed); `level` is its stored access level. */
export function featureCellValues(row: FeatureRow, column: FeatureColumnId, level: AccessLevel | null = null): string[] {
  if (column === 'feature') return [row.label];
  if (column === 'description') return [featureDescription(row.key)];
  const shown = shownLevel(row.choice, level);
  return shown ? [LEVEL_LABELS[shown]] : [];
}

/** What the search bar reads of a row: its name, key and description, whether it is not offered
 *  here, or changed by hand on its policy's page. */
export function featureSearchTexts(row: FeatureRow): string[] {
  return [
    row.label,
    row.key,
    featureDescription(row.key),
    row.offered ? '' : 'not offered',
    row.hand_edited ? 'changed by hand' : '',
  ];
}

export const FEATURE_EXPORT_HEADERS = ['Feature', 'Key', 'Description', 'Access', 'Offered here'];

/** A row of the CSV / Excel export, as the table shows it saved (`level`: its stored level). */
export function featureExportRow(row: FeatureRow, level: AccessLevel | null): string[] {
  const shown = shownLevel(row.choice, level);
  return [row.label, row.key, featureDescription(row.key), shown ? LEVEL_LABELS[shown] : '', row.offered ? 'Yes' : 'No'];
}
