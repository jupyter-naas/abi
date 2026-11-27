'use client';

/**
 * Settings → Search: the workspace's search topics.
 *
 * A topic is SPARQL templates whose variables fill the fixed slots of the
 * search page (results list, detail header, detail sections). Built-in topics
 * can be overridden and reset; custom topics can be added and deleted. Every
 * query is checked against its role's contract on save, and can be run on the
 * workspace graphs from here before it is.
 */
import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { ChevronDown, ChevronUp, Loader2, Play, Plus, RotateCcw, Search, Trash2 } from 'lucide-react';
import { TopicIcon, TOPIC_ICONS } from '@/components/search/topic-icon';
import { useConfirm, usePrompt } from '@/components/ui/dialogs';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Checkbox, radioClass } from '@/components/ui/checkbox';
import { fieldClass } from '@/components/ui/input';
import { InstanceHeader } from '@/components/access/instance-header';
import { FormSaveButton, InstanceBack, UnsavedBar } from '@/components/settings/instance-form';
import { usePageDraft, usePageState } from '@/hooks/use-page-state';
import {
  SettingsEmpty, SettingsLoading, SettingsNotice, SettingsPageHeader, SettingsTableToolbar,
} from '@/components/settings/settings-ui';
import {
  SettingsTableClear, SettingsTableHead, SettingsTableNoMatch, useSettingsTable,
} from '@/components/settings/users-table/settings-table';
import { TablePager } from '@/components/settings/users-table/table-pager';
import { BulkBar, SelectAllCell, SelectRowCell, onOffActions, useRowSelection, type RowSelection } from '@/components/settings/bulk-access';
import { UsersExportMenu } from '@/components/settings/users-table/users-table-actions';
import { downloadTableExport, type UsersExportFormat } from '@/components/settings/users-table/users-table-export';
import {
  blankTopic, searchHref,
  type PreviewResult, type QueryRole, type RoleContract, type SearchTopic, type TopicResultRowDef, type TopicSection,
} from '@/lib/search-topics';
import { TopicApiError, topicsApi } from '@/lib/search-topics-api';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { isFeatureEnabled } from '@/lib/feature-access';
import { SEARCH_SOURCE_IDS } from '@/lib/search-scopes';
import { createOfferApi } from '@/lib/access-model/workspace-offer';
import { policyOfSearch } from '@/components/settings/settings-policy';
import { useSearchTopicsStore } from '@/stores/search-topics';
import { useWorkspaceStore } from '@/stores/workspace';
import {
  SEARCH_COLUMNS, SEARCH_EXPORT_HEADERS, SOURCE_LABEL, entrySwitchable, searchCellValues, searchEntries, searchExportRow, searchSearchTexts,
  searchSortValue, type SearchEntry, type SearchGroup,
} from './search-settings-model';


/** The batch actions: enable or disable the entries selected. */
const BULK_ACTIONS = onOffActions({ on: 'Enable', off: 'Disable' });

/**
 * Settings → Search at one place: the table of its sources and topics, or a topic's page
 * (`topicId`, `search/topics/<id>`). Each route renders it.
 */
export function SearchSettingsView({ topicId = null }: { topicId?: string | null }) {
  return <Suspense fallback={null}><SearchSettings selectedId={topicId} /></Suspense>;
}

/** A topic's page under Settings → Search. */
export function searchTopicPath(workspaceId: string, topicId: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/settings/search/topics/${encodeURIComponent(topicId)}`;
}

function SearchSettings({ selectedId }: { selectedId: string | null }) {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const search = useSearchParams();
  // A former link (`?topic=`) opens the topic's page.
  const legacyTopic = !selectedId ? search?.get('topic') : null;
  useEffect(() => {
    if (legacyTopic) router.replace(searchTopicPath(workspaceId, legacyTopic));
  }, [legacyTopic, router, workspaceId]);
  // The policy picked in the Settings column (`?policy=`): the sources it grants are set here.
  const policy = policyOfSearch(search);
  const [policyDisabled, setPolicyDisabled] = useState<string[] | null>(null);
  const { topics: savedTopics, disabledScopes, setDisabledScopes, canEdit, loading, error, load, replace, remove } = useSearchTopicsStore();
  const workspace = useWorkspaceStore(state => state.getCurrentWorkspace());
  const [contract, setContract] = useState<Record<QueryRole, RoleContract> | null>(null);
  const prompt = usePrompt();
  // Topics created here and not saved yet exist only in the browser.
  // Kept across the list and a topic's page (`usePageState`): a reload of the topics drops them
  // from the store, they are drawn again from their ids.
  const [draftIds, setDraftIds] = usePageState<string[]>(
    workspaceId ? { scope: `workspace:${workspaceId}`, page: 'search', detail: 'new-topics' } : null,
    []
  );
  const drafts = useMemo(() => new Set(draftIds), [draftIds]);
  const setDrafts = (change: (current: Set<string>) => Set<string>) => setDraftIds((ids) => [...change(new Set(ids))]);
  const topics = useMemo(
    () => [...savedTopics, ...draftIds.filter((id) => !savedTopics.some((t) => t.id === id)).map((id) => blankTopic(id))],
    [savedTopics, draftIds]
  );

  useEffect(() => { if (workspaceId) void load(workspaceId, true); }, [workspaceId, load]);
  useEffect(() => { topicsApi.contract().then(setContract).catch(() => setContract(null)); }, []);
  useEffect(() => {
    setPolicyDisabled(null);
    if (!policy || !workspaceId) return;
    let cancelled = false;
    createOfferApi().read(workspaceId, policy).then(
      (state) => {
        const offered = new Set(state.offered?.search_sources ?? []);
        if (!cancelled) setPolicyDisabled(SEARCH_SOURCE_IDS.filter((id) => !offered.has(id)));
      },
      () => { if (!cancelled) setPolicyDisabled([...SEARCH_SOURCE_IDS]); },
    );
    return () => { cancelled = true; };
  }, [policy, workspaceId]);

  const graphs = useWorkspaceGraphs(workspaceId);
  const base = `/workspace/${encodeURIComponent(workspaceId)}/settings/search`;
  const selected = selectedId ? topics.find(t => t.id === selectedId) || null : null;
  const select = (id: string | null) => router.push(id ? searchTopicPath(workspaceId, id) : base, { scroll: false });

  const [toggling, setToggling] = useState<string | null>(null);
  const [tableError, setTableError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const failure = (e: unknown, fallback: string) =>
    e instanceof TopicApiError && e.errors.length ? e.errors.join('\n') : e instanceof Error ? e.message : fallback;
  /** One row switched: a feature or web engine (one switch each for the whole workspace), or a topic. */
  const switchEntry = async (entry: SearchEntry, enabled: boolean) => {
    if (entry.kind === 'topic') replace(await topicsApi.save(workspaceId, { ...entry.topic, enabled }));
    else {
      const after = (await topicsApi.setScopeEnabled(workspaceId, entry.id, enabled, policy)).disabled_scopes;
      if (policy) setPolicyDisabled(after);
      else setDisabledScopes(after);
    }
  };
  // A table of switches: each change saved at once, and said.
  const toggle = async (entry: SearchEntry, enabled: boolean) => {
    setToggling(entry.id); setTableError(null); setNotice('');
    try {
      await switchEntry(entry, enabled);
      setNotice(`${entry.name} ${enabled ? 'enabled' : 'disabled'}.`);
    } catch (e) {
      setTableError(failure(e, 'Could not change the entry'));
    } finally { setToggling(null); }
  };

  const createTopic = async () => {
    const id = await prompt.prompt({
      title: 'New search topic',
      description: 'Topic id: lowercase letters, digits, "-" or "_" (e.g. "project"). It cannot be changed later.',
      placeholder: 'project',
      confirmLabel: 'Create',
    });
    const clean = (id || '').trim().toLowerCase();
    if (!clean) return;
    if (topics.some(t => t.id === clean)) { select(clean); return; }
    replace(blankTopic(clean));
    setDrafts(d => new Set(d).add(clean));
    select(clean);
  };

  // One list for the table: topics, Nexus features and web engines.
  const role = workspace?.currentUserRole;
  const flags = workspace?.featureFlags;
  const entries = useMemo(
    () => searchEntries({
      topics, drafts, disabledScopes: policy ? (policyDisabled ?? [...SEARCH_SOURCE_IDS]) : disabledScopes,
      featureOn: scope => !scope.feature || isFeatureEnabled({ feature: scope.feature, role, workspaceFlags: flags }),
    }),
    [topics, drafts, disabledScopes, policy, policyDisabled, role, flags],
  );
  const table = useSettingsTable({
    rows: entries,
    columns: SEARCH_COLUMNS,
    cellValues: searchCellValues,
    searchTexts: searchSearchTexts,
    sortValue: searchSortValue,
    initialSort: 'group',
  });
  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(SEARCH_EXPORT_HEADERS, table.shown.map(searchExportRow), format, `search_${date}`, 'Search');
  };
  // The entries checked for a batch change (the rows shown: select all takes them).
  const selection = useRowSelection(useMemo(() => table.shown.map(entry => entry.id), [table.shown]));
  const switchable = (entry: SearchEntry) => entrySwitchable(entry, { canEdit, drafts });
  /** Enable or disable every selected entry that may change, one after the other. */
  const applyBulk = async (id: string) => {
    const enabled = id === 'on';
    const picked = entries.filter(entry => selection.selected.has(entry.id) && switchable(entry) && entry.on !== enabled);
    setToggling('bulk'); setTableError(null); setNotice('');
    let done = 0;
    try {
      for (const entry of picked) { await switchEntry(entry, enabled); done += 1; }
      setNotice(`${done} ${done === 1 ? 'entry' : 'entries'} ${enabled ? 'enabled' : 'disabled'}.`);
    } catch (e) {
      setTableError(`${failure(e, 'Could not change the entries')} (${done} of ${picked.length} changed)`);
    } finally { setToggling(null); }
  };

  if (selectedId) {
    return (
      <div className="space-y-6">
        <InstanceBack href={base} label="Search" />
        {loading && !selected ? (
          <SettingsLoading />
        ) : !selected ? (
          <SettingsEmpty title={<>There is no topic “{selectedId}” in this workspace.</>} />
        ) : (
          <TopicEditor
            key={`${selected.id}:${selected.source}`}
            workspaceId={workspaceId}
            topic={selected}
            topics={topics}
            graphs={graphs}
            contract={contract}
            canEdit={canEdit}
            isDraft={drafts.has(selected.id)}
            onSaved={(saved) => { replace(saved); setDrafts(d => { const n = new Set(d); n.delete(saved.id); return n; }); }}
            onReset={(restored) => { if (restored) replace(restored); else { remove(selected.id); select(null); } }}
            onDiscardNew={() => { remove(selected.id); setDrafts(d => { const n = new Set(d); n.delete(selected.id); return n; }); select(null); }}
          />
        )}
      </div>
    );
  }


  return (
    <div className="space-y-6">
      {prompt.dialog}
      <SettingsPageHeader
        title="Search"
        // One total: topics, features and web engines (the Enabled column says which are on).
        badge={`${entries.length} ${entries.length === 1 ? 'entry' : 'entries'}`}
        description={`${WORKSPACE_PAGE_DESCRIPTIONS['/settings/search']}. A disabled entry is gone from search for every member`}
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={table.shown.length === 0} />
            {canEdit && (
              <Button onClick={() => void createTopic()}>
                <Plus size={16} /> New topic
              </Button>
            )}
          </>
        }
      />

      {error && <SettingsNotice tone="error"><span role="alert">{error}</span></SettingsNotice>}
      {tableError && <SettingsNotice tone="error"><span role="alert" className="whitespace-pre-line">{tableError}</span></SettingsNotice>}
      {!canEdit && !loading && <SettingsNotice>Only workspace owners and admins can change search topics.</SettingsNotice>}
      {notice && <p className="text-xs text-muted-foreground" role="status" data-search-notice="">{notice}</p>}

      <SettingsTableToolbar
        search={table.search}
        onSearchChange={table.setSearch}
        searchPlaceholder="Search topics, features and engines..."
        // No count above the search: the badge says how many, the pager how many are shown.
        meta={<SettingsTableClear table={table} />}
      />
      <BulkBar
        selection={selection}
        noun="entry"
        plural="entries"
        actions={BULK_ACTIONS}
        onApply={applyBulk}
        skippedFor={() => entries.filter(entry => selection.selected.has(entry.id) && !switchable(entry)).length}
        change="this change"
        disabled={toggling !== null}
      />

      <div className="org-settings-users-table-wrap">
        <table className="org-settings-users-table">
          <SettingsTableHead
            table={table}
            leading={
              <SelectAllCell
                selection={selection}
                keys={table.shown.filter(switchable).map(entry => entry.id)}
                noun="entry"
                disabled={toggling !== null}
              />
            }
          />
          <tbody>
            {loading && !topics.length && (
              <tr><td colSpan={SEARCH_COLUMNS.length + 1} className="text-muted-foreground"><Loader2 size={14} className="mr-2 inline animate-spin" />Loading…</td></tr>
            )}
            {!loading && table.shown.length === 0 && <SettingsTableNoMatch colSpan={SEARCH_COLUMNS.length + 1} noun="entries" />}
            {table.paged.pageRows.map(entry => {
              const box = <SelectCell selection={selection} entry={entry} disabled={toggling !== null || !switchable(entry)} />;
              if (entry.kind === 'feature') {
                const { scope, available, on } = entry;
                return (
                  <ScopeRow key={entry.id} entry={entry} select={box}>
                    <EnabledSwitch label={scope.label} on={on} busy={toggling === scope.id}
                      disabled={!canEdit || !available || toggling === 'bulk'} onChange={() => void toggle(entry, !on)} />
                  </ScopeRow>
                );
              }
              if (entry.kind === 'engine') {
                const { engine, id, on } = entry;
                return (
                  <ScopeRow key={id} entry={entry} select={box}>
                    <EnabledSwitch label={engine.label} on={on} busy={toggling === id}
                      disabled={!canEdit || toggling === 'bulk'} onChange={() => void toggle(entry, !on)} />
                  </ScopeRow>
                );
              }
              const t = entry.topic;
              return (
                <tr key={t.id} data-entry={t.id} onClick={() => select(t.id)} className="cursor-pointer">
                  {box}
                  <td>
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center bg-muted"><TopicIcon name={t.icon} /></div>
                      <div className="min-w-0">
                        <div className={cn('font-medium', !t.enabled && 'text-muted-foreground')}>{t.plural_label}</div>
                        <div className="font-mono text-xs text-muted-foreground">{t.id}</div>
                      </div>
                    </div>
                  </td>
                  <td><GroupBadge group={entry.group} /></td>
                  <td className="text-muted-foreground">{entry.type}</td>
                  <td onClick={e => e.stopPropagation()}>
                    <EnabledSwitch
                      label={t.plural_label}
                      on={t.enabled}
                      busy={toggling === t.id}
                      disabled={!canEdit || drafts.has(t.id) || toggling === 'bulk'}
                      onChange={() => void toggle(entry, !t.enabled)}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <TablePager total={table.shown.length} paged={table.paged} />
    </div>
  );
}

function GroupBadge({ group }: { group: SearchGroup }) {
  return <Badge variant="outline">{group}</Badge>;
}

/** A row's box for a batch change. */
function SelectCell({ selection, entry, disabled }: { selection: RowSelection; entry: SearchEntry; disabled: boolean }) {
  return <SelectRowCell selection={selection} rowKey={entry.id} label={entry.name} disabled={disabled} />;
}

/** A feature or web-engine row: nothing to edit but whether search may use it. */
function ScopeRow({ entry, select, children }: { entry: Exclude<SearchEntry, { kind: 'topic' }>; select: React.ReactNode; children: React.ReactNode }) {
  const icon = entry.kind === 'feature' ? entry.scope.icon : entry.engine.icon;
  return (
    <tr data-entry={entry.id}>
      {select}
      <td>
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center bg-muted"><TopicIcon name={icon} /></div>
          <div className="min-w-0">
            <div className="font-medium">{entry.name}</div>
            <div className="truncate text-xs text-muted-foreground" title={entry.description}>{entry.description}</div>
          </div>
        </div>
      </td>
      <td><GroupBadge group={entry.group} /></td>
      <td className="text-muted-foreground">{entry.type}</td>
      <td><span className="sr-only">{entry.id}</span>{children}</td>
    </tr>
  );
}

interface WorkspaceGraph { uri: string; label: string }

/** Graphs this workspace can read (the graph picker's list). */
function useWorkspaceGraphs(workspaceId: string): WorkspaceGraph[] | null {
  const [graphs, setGraphs] = useState<WorkspaceGraph[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    authFetch(`${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`)
      .then(r => (r.ok ? r.json() : []))
      .then((packs: { graphs: { uri: string; label: string }[] }[]) => {
        if (cancelled) return;
        const seen = new Map<string, WorkspaceGraph>();
        for (const pack of packs) for (const g of pack.graphs) if (!seen.has(g.uri)) seen.set(g.uri, { uri: g.uri, label: g.label || g.uri });
        setGraphs([...seen.values()].sort((a, b) => a.label.localeCompare(b.label)));
      })
      .catch(() => { if (!cancelled) setGraphs([]); });
    return () => { cancelled = true; };
  }, [workspaceId]);
  return graphs;
}

function EnabledSwitch({ label, on, busy, disabled, onChange }: { label: string; on: boolean; busy?: boolean; disabled?: boolean; onChange: () => void }) {
  return (
    <span className="inline-flex items-center gap-2">
      <Checkbox checked={on} disabled={disabled || busy} onCheckedChange={onChange} aria-label={`${label} enabled`} />
      {busy && <Loader2 size={12} className="animate-spin text-muted-foreground" />}
    </span>
  );
}

function TopicEditor({ workspaceId, topic, topics, graphs, contract, canEdit, isDraft, onSaved, onReset, onDiscardNew }: {
  workspaceId: string;
  topic: SearchTopic;
  topics: SearchTopic[];
  graphs: WorkspaceGraph[] | null;
  contract: Record<QueryRole, RoleContract> | null;
  canEdit: boolean;
  isDraft: boolean;
  onSaved: (topic: SearchTopic) => void;
  onReset: (restored: SearchTopic | null) => void;
  onDiscardNew: () => void;
}) {
  // The topic as saved, and the edits over it, kept for a return to the page (one field: the
  // topic's JSON, its queries and lists included).
  const server = useMemo(() => ({ topic: JSON.stringify(topic) }), [topic]);
  const page = usePageDraft({ scope: `workspace:${workspaceId}`, page: 'search', detail: `topic:${topic.id}` }, server);
  const edited = page.values?.topic ?? server.topic;
  const draft: SearchTopic = useMemo(() => JSON.parse(edited) as SearchTopic, [edited]);
  const draftRef = useRef(draft);
  draftRef.current = draft;
  const setDraft = (next: SearchTopic | ((current: SearchTopic) => SearchTopic)) => {
    const value = typeof next === 'function' ? next(draftRef.current) : next;
    draftRef.current = value;
    setSaved(false);
    page.set({ topic: JSON.stringify(value) });
  };
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [testUri, setTestUri] = useState('');
  const confirm = useConfirm();
  const dirty = edited !== server.topic;

  const set = <K extends keyof SearchTopic>(key: K, value: SearchTopic[K]) => setDraft(d => ({ ...d, [key]: value }));
  const setSection = (index: number, patch: Partial<TopicSection>) =>
    setDraft(d => ({ ...d, sections: d.sections.map((s, i) => (i === index ? { ...s, ...patch } : s)) }));
  // Result rows and detail facts are both lists of `row` queries.
  type RowList = 'result_rows' | 'detail_facts';
  const rowsOf = (d: SearchTopic, key: RowList) => d[key] ?? [];
  const setRow = (key: RowList, index: number, patch: Partial<TopicResultRowDef>) =>
    setDraft(d => ({ ...d, [key]: rowsOf(d, key).map((r, i) => (i === index ? { ...r, ...patch } : r)) }));
  const moveRow = (key: RowList, index: number, delta: number) => setDraft(d => {
    const rows = [...rowsOf(d, key)];
    const [moved] = rows.splice(index, 1);
    rows.splice(Math.max(0, Math.min(rows.length, index + delta)), 0, moved!);
    return { ...d, [key]: rows };
  });
  const rowListEditor = (key: RowList, { title, help, empty, noun, template }: { title: string; help: string; empty: string; noun: string; template: string }) => {
    const rows = rowsOf(draft, key);
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold">{title}</h4>
          {canEdit && (
            <button type="button" onClick={() => set(key, [...rows, { id: `${noun}_${rows.length + 1}`, label: `New ${noun}`, query: template }])}
              className={cn(buttonVariants({ variant: 'secondary', size: 'sm' }))}><Plus size={14} /> Add {noun}</button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">{help}</p>
        {rows.length === 0 && <p className="text-sm text-muted-foreground">{empty}</p>}
        {rows.map((row, index) => (
          <div key={index} className="space-y-3 border border-border bg-card p-3">
            <fieldset disabled={disabled} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
              <Field label="Id"><input className={cn(input, 'font-mono text-xs')} value={row.id} onChange={e => setRow(key, index, { id: e.target.value })} /></Field>
              <Field label="Label"><input className={input} value={row.label} onChange={e => setRow(key, index, { label: e.target.value })} /></Field>
              <div className="flex items-end gap-1 pb-0.5">
                <IconButton label="Move up" onClick={() => moveRow(key, index, -1)} disabled={index === 0}><ChevronUp size={14} /></IconButton>
                <IconButton label="Move down" onClick={() => moveRow(key, index, 1)} disabled={index === rows.length - 1}><ChevronDown size={14} /></IconButton>
                <IconButton label={`Remove ${noun}`} onClick={() => set(key, rows.filter((_, i) => i !== index))}><Trash2 size={14} /></IconButton>
              </div>
            </fieldset>
            <QueryEditor role="row" label="Query" contract={contract?.row} value={row.query} disabled={disabled}
              onChange={v => setRow(key, index, { query: v })} workspaceId={workspaceId} testUri={testUri} canEdit={canEdit} graphs={draft.graphs} />
          </div>
        ))}
      </div>
    );
  };
  const moveSection = (index: number, delta: number) => setDraft(d => {
    const sections = [...d.sections];
    const [moved] = sections.splice(index, 1);
    sections.splice(Math.max(0, Math.min(sections.length, index + delta)), 0, moved!);
    return { ...d, sections };
  });

  const save = async () => {
    setSaving(true); setErrors([]);
    try {
      const result = await topicsApi.save(workspaceId, draft);
      page.discard();
      onSaved(result); setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      setErrors(error instanceof TopicApiError && error.errors.length ? error.errors : [error instanceof Error ? error.message : 'Save failed']);
    } finally { setSaving(false); }
  };

  const reset = async () => {
    const builtin = topic.source !== 'custom';
    const ok = await confirm.confirm({
      title: builtin ? `Reset ${topic.plural_label}?` : `Delete ${topic.plural_label}?`,
      description: builtin ? 'The shipped definition replaces this workspace’s changes.' : 'The topic disappears from the search page of this workspace.',
      confirmLabel: builtin ? 'Reset' : 'Delete',
    });
    if (!ok) return;
    if (isDraft) { onDiscardNew(); return; }
    try { onReset((await topicsApi.reset(workspaceId, topic.id)).topic); }
    catch (error) { setErrors([error instanceof Error ? error.message : 'Reset failed']); }
  };

  const disabled = !canEdit;
  const input = cn(fieldClass, 'h-9');

  return (
    <div className="min-w-0 space-y-5">
      {confirm.dialog}
      {/* The header of an instance's page: its name, its id, where it comes from; Save at its right,
          faded until something changes (a topic not saved yet: at once). */}
      <InstanceHeader
        name={
          <span className="inline-flex items-center gap-2">
            <TopicIcon name={draft.icon} size={18} />
            {draft.plural_label}
          </span>
        }
        id={topic.id}
        badge={<Badge>{SOURCE_LABEL[topic.source]}</Badge>}
        meta={
          <a href={searchHref(workspaceId, { scope: topic.id })} className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
            <Search size={12} /> Open in search
          </a>
        }
        actions={
          canEdit ? (
            <>
              {topic.source !== 'builtin' && (
                <Button variant={topic.source === 'override' ? 'secondary' : 'destructive-ghost'} onClick={() => void reset()}>
                  {topic.source === 'override' ? <><RotateCcw size={14} /> Reset</> : <><Trash2 size={14} /> Delete</>}
                </Button>
              )}
              <FormSaveButton dirty={dirty || isDraft} saving={saving} saved={saved} onSave={() => void save()} />
            </>
          ) : undefined
        }
      />
      <UnsavedBar show={canEdit && dirty} onDiscard={page.discard} disabled={saving} />
      {errors.length > 0 && (
        <SettingsNotice tone="error">
          <ul role="alert" className="list-disc space-y-0.5 pl-4">
            {errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </SettingsNotice>
      )}

      <fieldset disabled={disabled} className="grid gap-3 sm:grid-cols-2">
        <Field label="Label (singular)"><input className={input} value={draft.label} onChange={e => set('label', e.target.value)} /></Field>
        <Field label="Label (plural, tab name)"><input className={input} value={draft.plural_label} onChange={e => set('plural_label', e.target.value)} /></Field>
        <Field label="Detail tab label" hint="The tab that shows one individual, after Results and Ontology (e.g. Profile, Card).">
          <input className={input} value={draft.detail_label} onChange={e => set('detail_label', e.target.value)} placeholder="Details" />
        </Field>
        <Field label="Description" wide><input className={input} value={draft.description} onChange={e => set('description', e.target.value)} /></Field>
        <Field label="Ontology class IRI" hint="Shown in the Ontology tab of the topic." wide>
          <input className={cn(input, 'font-mono text-xs')} value={draft.class_iri} onChange={e => set('class_iri', e.target.value)} placeholder="http://ontology.naas.ai/abi/Person" />
        </Field>
        <Field label="Icon">
          <select className={input} value={draft.icon} onChange={e => set('icon', e.target.value)}>
            {Object.keys(TOPIC_ICONS).map(name => <option key={name} value={name}>{name}</option>)}
          </select>
        </Field>
        <div className="flex items-end gap-4">
          <Field label="Order"><input type="number" className={input} value={draft.order} onChange={e => set('order', Number(e.target.value) || 0)} /></Field>
          <Checkbox className="h-9" label="Enabled" checked={draft.enabled} onCheckedChange={v => set('enabled', v)} />
        </div>
      </fieldset>

      <fieldset disabled={disabled} className="space-y-2">
        <legend className="mb-1 text-sm font-medium text-foreground">Graphs</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" className={radioClass} checked={draft.graphs.length === 0} onChange={() => set('graphs', [])} />
          All graphs this workspace can read <span className="text-xs text-muted-foreground">(default)</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" className={radioClass} checked={draft.graphs.length > 0}
            onChange={() => { if (!draft.graphs.length && graphs?.length) set('graphs', [graphs[0]!.uri]); }}
            disabled={!graphs?.length} />
          Only these graphs
        </label>
        {draft.graphs.length > 0 && (
          <div className="ml-6 max-h-56 space-y-1 overflow-auto border border-border p-2">
            {(graphs || []).map(g => (
              <label key={g.uri} className="flex cursor-pointer items-center gap-2 text-sm" title={g.uri}>
                <Checkbox
                  checked={draft.graphs.includes(g.uri)}
                  onCheckedChange={checked => {
                    const next = checked ? [...draft.graphs, g.uri] : draft.graphs.filter(u => u !== g.uri);
                    if (next.length) set('graphs', next);
                  }}
                />
                <span className="truncate">{g.label}</span>
                <span className="truncate font-mono text-micro text-muted-foreground">{g.uri}</span>
              </label>
            ))}
            {draft.graphs.filter(u => !graphs?.some(g => g.uri === u)).map(u => (
              <p key={u} className="text-xs text-amber-600 dark:text-amber-400">{u} is not readable in this workspace: the topic skips it here.</p>
            ))}
          </div>
        )}
      </fieldset>

      <div className="border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
        <p className="mb-1 font-medium text-foreground">How queries are filled in</p>
        <p>
          <code>{'{{ q }}'}</code> is the text typed in the search box (write it inside quotes), <code>{'{{ uri }}'}</code> the selected
          individual as an IRI, <code>{'{{ limit }}'}</code>/<code>{'{{ offset }}'}</code> paging, <code>{'{{ uris }}'}</code> the page of
          results for the image and row queries (write <code>{'VALUES ?uri { {{ uris }} }'}</code>). Do not use <code>FROM</code>, <code>SERVICE</code> or a
          fixed <code>GRAPH</code>: queries read the graphs this workspace can read.
        </p>
        <label className="mt-2 flex items-center gap-2">
          <span className="shrink-0">Test individual</span>
          <input className={cn(input, 'font-mono text-xs')} value={testUri} onChange={e => setTestUri(e.target.value)} placeholder="IRI used by Test on the image, row, header and section queries — Test the results query to pick one" />
        </label>
      </div>

      <QueryEditor role="results" label="Results query" contract={contract?.results} value={draft.results_query} disabled={disabled}
        onChange={v => set('results_query', v)} workspaceId={workspaceId} testUri={testUri} onPickUri={setTestUri} canEdit={canEdit} graphs={draft.graphs} />
      <QueryEditor role="image" label="Image query" contract={contract?.image} value={draft.image_query} disabled={disabled}
        hint="The picture of each result, e.g. a person's portrait. Leave empty to use ?image from the results query, or initials."
        placeholder={IMAGE_QUERY_TEMPLATE}
        onChange={v => set('image_query', v)} workspaceId={workspaceId} testUri={testUri} canEdit={canEdit} graphs={draft.graphs} />

      {rowListEditor('result_rows', {
        title: 'Result rows',
        help: 'Each row is one labelled line of metadata under every result. Several values are joined.',
        empty: 'No rows: results show their title and subtitle only.',
        noun: 'row',
        template: ROW_QUERY_TEMPLATE,
      })}

      <QueryEditor role="header" label="Detail header query" contract={contract?.header} value={draft.header_query} disabled={disabled}
        onChange={v => set('header_query', v)} workspaceId={workspaceId} testUri={testUri} canEdit={canEdit} graphs={draft.graphs} />

      {rowListEditor('detail_facts', {
        title: 'Detail facts',
        help: "Facts added to the detail header, in order, after the header query's own (e.g. a service line or a grade). {{ uris }} is the individual shown.",
        empty: 'No extra facts: the header shows the header query only.',
        noun: 'fact',
        template: ROW_QUERY_TEMPLATE,
      })}

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold">Detail sections</h4>
          {canEdit && (
            <button type="button" onClick={() => set('sections', [...draft.sections, { id: `section_${draft.sections.length + 1}`, label: 'New section', empty_text: 'Nothing recorded.', link_topic: null, query: 'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nSELECT ?title ?item\nWHERE {\n  {{ uri }} ?p ?item .\n  ?item rdfs:label ?title .\n}\nLIMIT {{ limit }}' }])}
              className={cn(buttonVariants({ variant: 'secondary', size: 'sm' }))}><Plus size={14} /> Add section</button>
          )}
        </div>
        {draft.sections.length === 0 && <p className="text-sm text-muted-foreground">No sections: the detail shows the header only.</p>}
        {draft.sections.map((section, index) => (
          <div key={index} className="space-y-3 border border-border bg-card p-3">
            <fieldset disabled={disabled} className="grid gap-3 sm:grid-cols-[1fr_1fr_1fr_auto]">
              <Field label="Id"><input className={cn(input, 'font-mono text-xs')} value={section.id} onChange={e => setSection(index, { id: e.target.value })} /></Field>
              <Field label="Label"><input className={input} value={section.label} onChange={e => setSection(index, { label: e.target.value })} /></Field>
              <Field label="?item opens topic">
                <select className={input} value={section.link_topic || ''} onChange={e => setSection(index, { link_topic: e.target.value || null })}>
                  <option value="">— none —</option>
                  {topics.map(t => <option key={t.id} value={t.id}>{t.plural_label}</option>)}
                </select>
              </Field>
              <div className="flex items-end gap-1 pb-0.5">
                <IconButton label="Move up" onClick={() => moveSection(index, -1)} disabled={index === 0}><ChevronUp size={14} /></IconButton>
                <IconButton label="Move down" onClick={() => moveSection(index, 1)} disabled={index === draft.sections.length - 1}><ChevronDown size={14} /></IconButton>
                <IconButton label="Remove section" onClick={() => set('sections', draft.sections.filter((_, i) => i !== index))}><Trash2 size={14} /></IconButton>
              </div>
              <Field label="Text when empty" wide><input className={input} value={section.empty_text} onChange={e => setSection(index, { empty_text: e.target.value })} /></Field>
            </fieldset>
            <QueryEditor role="section" label="Query" contract={contract?.section} value={section.query} disabled={disabled}
              onChange={v => setSection(index, { query: v })} workspaceId={workspaceId} testUri={testUri} canEdit={canEdit} graphs={draft.graphs} />
          </div>
        ))}
      </div>
    </div>
  );
}

const IMAGE_QUERY_TEMPLATE = `PREFIX abi: <http://ontology.naas.ai/abi/>
SELECT ?uri ?image
WHERE {
  VALUES ?uri { {{ uris }} }
  ?uri abi:hasPortrait ?p .
  ?p abi:portrait_url ?image .
}`;

const ROW_QUERY_TEMPLATE = `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?uri ?value
WHERE {
  VALUES ?uri { {{ uris }} }
  ?uri ?p ?o .
  ?o rdfs:label ?value .
}`;

function QueryEditor({ role, label, hint, placeholder, contract, value, onChange, disabled, workspaceId, testUri, onPickUri, canEdit, graphs }: {
  role: QueryRole;
  label: string;
  hint?: string;
  placeholder?: string;
  contract?: RoleContract;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  workspaceId: string;
  testUri: string;
  onPickUri?: (uri: string) => void;
  canEdit: boolean;
  graphs: string[];
}) {
  const [testQ, setTestQ] = useState('');
  const [running, setRunning] = useState(false);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setRunning(true); setError(null);
    try {
      const params: Record<string, string> = role === 'results' ? { q: testQ } : { uri: testUri.trim() };
      setPreview(await topicsApi.preview(workspaceId, role, value, params, graphs));
    } catch (e) {
      setPreview(null);
      setError(e instanceof TopicApiError && e.errors.length ? e.errors.join('\n') : e instanceof Error ? e.message : 'Query failed');
    } finally { setRunning(false); }
  };

  const columns = preview ? [...new Set(preview.rows.flatMap(r => Object.keys(r)))] : [];
  const slots = new Set([...(contract?.required || []), ...(contract?.optional || [])]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium">{label}</span>
        {contract && (
          <span className="text-caption text-muted-foreground">
            needs {contract.required.map(v => `?${v}`).join(' ')}{contract.optional.length > 0 && <> · may use {contract.optional.map(v => `?${v}`).join(' ')}</>}
            {contract.extra_as_facts && ' · other variables show as facts'}
          </span>
        )}
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        spellCheck={false}
        rows={Math.min(24, Math.max(6, (value || placeholder || '').split('\n').length + 1))}
        placeholder={placeholder}
        className={cn(fieldClass, 'bg-muted/30 p-2 font-mono text-xs leading-relaxed disabled:opacity-80')}
        aria-label={label}
      />
      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          {role === 'results' && (
            <input value={testQ} onChange={e => setTestQ(e.target.value)} placeholder="Test text for {{ q }} (empty lists all)"
              className={cn(fieldClass, 'h-8 min-w-0 flex-1 text-xs')} />
          )}
          <Button variant="secondary" size="sm" onClick={() => void run()} disabled={running || !value.trim() || (role !== 'results' && !testUri.trim())}
            title={role !== 'results' && !testUri.trim() ? 'Set a test individual first' : undefined}>
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Test
          </Button>
        </div>
      )}
      {error && <pre role="alert" className="whitespace-pre-wrap border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">{error}</pre>}
      {preview && (
        <div className="overflow-auto border border-border">
          <table className="w-full text-xs">
            <thead className="bg-muted/50">
              <tr>{columns.map(c => <th key={c} className={cn('px-2 py-1 text-left font-mono font-medium', slots.has(c) ? 'text-primary' : 'text-muted-foreground')}>?{c}</th>)}</tr>
            </thead>
            <tbody>
              {preview.rows.length === 0 && <tr><td className="px-2 py-2 text-muted-foreground">No rows.</td></tr>}
              {preview.rows.map((row, i) => (
                <tr key={i} className="border-t">
                  {columns.map(c => {
                    const cell = row[c];
                    const pick = role === 'results' && c === 'uri' && cell && onPickUri;
                    return (
                      <td key={c} className="max-w-64 truncate px-2 py-1" title={cell?.value}>
                        {pick ? <button type="button" className="text-primary hover:underline" onClick={() => onPickUri(cell.value)} title="Use as test individual">{cell.value}</button> : cell?.value}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Field({ label, hint, wide, children }: { label: string; hint?: string; wide?: boolean; children: React.ReactNode }) {
  return (
    <label className={cn('block space-y-1', wide && 'sm:col-span-full')}>
      <span className="text-sm font-medium text-foreground">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}

function IconButton({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
  return (
    <Button variant="ghost" size="icon" className="h-9 w-9" aria-label={label} title={label} onClick={onClick} disabled={disabled}>
      {children}
    </Button>
  );
}
