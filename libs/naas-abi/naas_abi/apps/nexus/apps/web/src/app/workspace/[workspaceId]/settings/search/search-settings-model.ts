/**
 * Settings › Search, laid out as Settings › Users: one row per search topic, Nexus feature and web
 * engine, the table's columns (search, sort, filter, export). Pure: the view is `page.tsx`.
 */
import type { SettingsColumn } from '@/components/settings/users-table/settings-table';
import type { SearchTopic } from '@/lib/search-topics';
import { FEATURE_SCOPES, WEB_ENGINES, webEngineScopeId, type SearchScope } from '@/lib/search-scopes';

export const SOURCE_LABEL: Record<SearchTopic['source'], string> = {
  builtin: 'Built-in',
  override: 'Customized',
  custom: 'Custom',
};

export type SearchGroup = 'Custom' | 'Workspace' | 'Web';
/** Topics first, then the Nexus features, then the web engines. */
const GROUP_ORDER: SearchGroup[] = ['Custom', 'Workspace', 'Web'];

type WebEngine = (typeof WEB_ENGINES)[number];
type EntryBase = {
  /** The row's id: the topic id, the scope id, or `web.<engine>`. */
  id: string;
  name: string;
  group: SearchGroup;
  type: string;
  on: boolean;
  description: string;
};

/** A row of the table: a topic, a Nexus feature or a web engine. */
export type SearchEntry =
  | (EntryBase & { kind: 'topic'; topic: SearchTopic })
  | (EntryBase & { kind: 'feature'; scope: SearchScope; available: boolean })
  | (EntryBase & { kind: 'engine'; engine: WebEngine });

/** Every row, topics first: a feature off in the workspace is listed, never on. */
export function searchEntries({
  topics,
  drafts,
  disabledScopes,
  featureOn,
}: {
  topics: readonly SearchTopic[];
  /** Topics created here and not saved yet. */
  drafts: ReadonlySet<string>;
  disabledScopes: readonly string[];
  featureOn: (scope: SearchScope) => boolean;
}): SearchEntry[] {
  return [
    ...topics.map(
      (topic): SearchEntry => ({
        kind: 'topic',
        topic,
        id: topic.id,
        name: topic.plural_label,
        group: 'Custom',
        type: drafts.has(topic.id) ? 'Draft' : SOURCE_LABEL[topic.source],
        on: topic.enabled,
        description: '',
      }),
    ),
    ...FEATURE_SCOPES.map((scope): SearchEntry => {
      const available = featureOn(scope);
      return {
        kind: 'feature',
        scope,
        available,
        id: scope.id,
        name: scope.label,
        group: 'Workspace',
        type: 'Nexus feature',
        on: available && !disabledScopes.includes(scope.id),
        description: available
          ? scope.description
          : `${scope.description} — the ${scope.label} feature is off in this workspace`,
      };
    }),
    ...WEB_ENGINES.map((engine): SearchEntry => {
      const id = webEngineScopeId(engine.id);
      return {
        kind: 'engine',
        engine,
        id,
        name: engine.label,
        group: 'Web',
        type: 'Web engine',
        on: !disabledScopes.includes(id),
        description: `${engine.description} — the query leaves Nexus`,
      };
    }),
  ];
}

export type SearchColumnId = 'name' | 'group' | 'type' | 'enabled';
export const SEARCH_COLUMNS: SettingsColumn<SearchColumnId>[] = [
  { id: 'name', label: 'Name' },
  { id: 'group', label: 'Group' },
  { id: 'type', label: 'Type' },
  { id: 'enabled', label: 'Enabled', className: 'w-28' },
];

const enabledLabel = (on: boolean) => (on ? 'Enabled' : 'Disabled');

/** What a column filter sees of a row. */
export function searchCellValues(entry: SearchEntry, column: SearchColumnId): string[] {
  if (column === 'name') return [entry.name];
  if (column === 'group') return [entry.group];
  if (column === 'type') return [entry.type];
  return [enabledLabel(entry.on)];
}

/** What a column sorts on: groups in their own order (topics, features, engines). */
export function searchSortValue(entry: SearchEntry, column: SearchColumnId): string | number {
  if (column === 'group') return GROUP_ORDER.indexOf(entry.group);
  return searchCellValues(entry, column).join(', ');
}

/** What the search bar reads of a row. */
export function searchSearchTexts(entry: SearchEntry): string[] {
  return [entry.name, entry.id, entry.description, entry.group, entry.type];
}

export const SEARCH_EXPORT_HEADERS = ['Name', 'Id', 'Group', 'Type', 'Enabled'];

export function searchExportRow(entry: SearchEntry): string[] {
  return [entry.name, entry.id, entry.group, entry.type, entry.on ? 'Yes' : 'No'];
}

/** Whether a row's switch may change: the caller edits search, a feature is on in the workspace,
 *  a topic is saved (a draft is not). */
export function entrySwitchable(entry: SearchEntry, { canEdit, drafts }: { canEdit: boolean; drafts: ReadonlySet<string> }): boolean {
  if (!canEdit) return false;
  if (entry.kind === 'feature') return entry.available;
  if (entry.kind === 'topic') return !drafts.has(entry.id);
  return true;
}
