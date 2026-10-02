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
import { Suspense, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, ChevronDown, ChevronUp, Loader2, Play, Plus, RotateCcw, Save, Search, Trash2 } from 'lucide-react';
import { TopicIcon, TOPIC_ICONS } from '@/components/search/topic-icon';
import { useConfirm, usePrompt } from '@/components/ui/dialogs';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Checkbox, radioClass } from '@/components/ui/checkbox';
import { fieldClass } from '@/components/ui/input';
import { SettingsReloadButton } from '@/components/settings/settings-reload';
import {
  SettingsEmpty, SettingsFilterSelect, SettingsLoading, SettingsNotice, SettingsPageHeader, SettingsTableToolbar, countLabel, settingsTable,
} from '@/components/settings/settings-ui';
import {
  blankTopic, searchHref,
  type PreviewResult, type QueryRole, type RoleContract, type SearchTopic, type TopicResultRowDef, type TopicSection,
} from '@/lib/search-topics';
import { TopicApiError, topicsApi } from '@/lib/search-topics-api';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { isFeatureEnabled, type FeatureKey } from '@/lib/feature-access';
import { FEATURE_SCOPES, WEB_ENGINES, webEngineScopeId } from '@/lib/search-scopes';
import { useSearchTopicsStore } from '@/stores/search-topics';
import { useWorkspaceStore } from '@/stores/workspace';

const SOURCE_LABEL: Record<SearchTopic['source'], string> = { builtin: 'Built-in', override: 'Customized', custom: 'Custom' };

export default function SearchSettingsPage() {
  return <Suspense fallback={null}><SearchSettings /></Suspense>;
}

function SearchSettings() {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const selectedId = useSearchParams()?.get('topic');
  const { topics, disabledScopes, setDisabledScopes, canEdit, loading, error, load, replace, remove } = useSearchTopicsStore();
  const workspace = useWorkspaceStore(state => state.getCurrentWorkspace());
  const featureOn = (feature?: FeatureKey) => !feature || isFeatureEnabled({
    feature, role: workspace?.currentUserRole, workspaceFlags: workspace?.featureFlags,
  });
  const [contract, setContract] = useState<Record<QueryRole, RoleContract> | null>(null);
  const prompt = usePrompt();
  // Topics created here and not saved yet exist only in the browser.
  const [drafts, setDrafts] = useState<Set<string>>(new Set());

  useEffect(() => { if (workspaceId) void load(workspaceId, true); }, [workspaceId, load]);
  useEffect(() => { topicsApi.contract().then(setContract).catch(() => setContract(null)); }, []);

  const graphs = useWorkspaceGraphs(workspaceId);
  const base = `/workspace/${encodeURIComponent(workspaceId)}/settings/search`;
  const selected = selectedId ? topics.find(t => t.id === selectedId) || null : null;
  const select = (id: string | null) => router.push(id ? `${base}?topic=${encodeURIComponent(id)}` : base, { scroll: false });

  const [toggling, setToggling] = useState<string | null>(null);
  const [tableError, setTableError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [groupFilter, setGroupFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  // Features and web engines: one switch each for the whole workspace.
  const toggleScope = async (scopeId: string, enabled: boolean) => {
    setToggling(scopeId); setTableError(null);
    try {
      setDisabledScopes((await topicsApi.setScopeEnabled(workspaceId, scopeId, enabled)).disabled_scopes);
    } catch (e) {
      setTableError(e instanceof Error ? e.message : 'Could not change the scope');
    } finally { setToggling(null); }
  };

  const toggleEnabled = async (topic: SearchTopic) => {
    setToggling(topic.id); setTableError(null);
    try {
      replace(await topicsApi.save(workspaceId, { ...topic, enabled: !topic.enabled }));
    } catch (e) {
      setTableError(e instanceof TopicApiError && e.errors.length ? e.errors.join('\n') : e instanceof Error ? e.message : 'Could not change the topic');
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

  if (selectedId) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-2">
          <Button variant="secondary" onClick={() => select(null)}>
            <ArrowLeft size={16} /> All topics
          </Button>
          <SettingsReloadButton />
        </div>
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

  // One list for the table: topics, Nexus features and web engines, each with what the filters need.
  const query = searchQuery.trim().toLowerCase();
  const matches = (group: string, on: boolean, ...texts: string[]) =>
    (groupFilter === 'all' || groupFilter === group) &&
    (statusFilter === 'all' || (statusFilter === 'enabled') === on) &&
    (!query || texts.some(text => text.toLowerCase().includes(query)));
  const featureRows = FEATURE_SCOPES.map(scope => {
    const available = featureOn(scope.feature);
    return { scope, available, on: available && !disabledScopes.includes(scope.id) };
  });
  const engineRows = WEB_ENGINES.map(engine => {
    const id = webEngineScopeId(engine.id);
    return { engine, id, on: !disabledScopes.includes(id) };
  });
  const shownTopics = topics.filter(t => matches('Custom', t.enabled, t.plural_label, t.id));
  const shownFeatures = featureRows.filter(r => matches('Workspace', r.on, r.scope.label, r.scope.id, r.scope.description));
  const shownEngines = engineRows.filter(r => matches('Web', r.on, r.engine.label, r.id, r.engine.description));
  const totalRows = topics.length + featureRows.length + engineRows.length;
  const shownRows = shownTopics.length + shownFeatures.length + shownEngines.length;
  const enabledRows = topics.filter(t => t.enabled).length + featureRows.filter(r => r.on).length + engineRows.filter(r => r.on).length;

  return (
    <div className="space-y-6">
      {prompt.dialog}
      <SettingsPageHeader
        title="Search"
        badge={`${enabledRows} enabled`}
        description="What the search page of this workspace can look into. A disabled entry disappears from search for every member. Topics read every graph this workspace can read, unless a topic is limited to some of them."
        actions={
          canEdit && (
            <Button onClick={() => void createTopic()}>
              <Plus size={16} /> New topic
            </Button>
          )
        }
      />

      {error && <SettingsNotice tone="error"><span role="alert">{error}</span></SettingsNotice>}
      {tableError && <SettingsNotice tone="error"><span role="alert" className="whitespace-pre-line">{tableError}</span></SettingsNotice>}
      {!canEdit && !loading && <SettingsNotice>Only workspace owners and admins can change search topics.</SettingsNotice>}

      <SettingsTableToolbar
        search={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search topics, features and engines..."
        filters={
          <>
            <SettingsFilterSelect
              label="Group"
              value={groupFilter}
              onChange={setGroupFilter}
              options={[
                { value: 'all', label: 'All groups' },
                { value: 'Custom', label: 'Custom' },
                { value: 'Workspace', label: 'Workspace' },
                { value: 'Web', label: 'Web' },
              ]}
            />
            <SettingsFilterSelect
              label="Status"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'All statuses' },
                { value: 'enabled', label: 'Enabled' },
                { value: 'disabled', label: 'Disabled' },
              ]}
            />
          </>
        }
        meta={`${countLabel(shownRows, totalRows, 'entry', 'entries')} · ${enabledRows} enabled · ${topics.length} topic${topics.length === 1 ? '' : 's'}`}
      />

      <div className={settingsTable.wrapper}>
        <table className={settingsTable.table}>
          <thead>
            <tr className={settingsTable.headRow}>
              <th className={settingsTable.th}>Name</th>
              <th className={settingsTable.th}>Group</th>
              <th className={settingsTable.th}>Type</th>
              <th className={cn(settingsTable.th, 'w-24')}>Enabled</th>
            </tr>
          </thead>
          <tbody>
            {loading && !topics.length && (
              <tr><td colSpan={4} className={cn(settingsTable.td, 'text-muted-foreground')}><Loader2 size={14} className="mr-2 inline animate-spin" />Loading…</td></tr>
            )}
            {!loading && shownRows === 0 && (
              <tr><td colSpan={4} className="p-8 text-center text-muted-foreground">No entries match the current search and filters</td></tr>
            )}
            {shownTopics.map(t => (
              <tr key={t.id} onClick={() => select(t.id)} className={cn(settingsTable.row, 'cursor-pointer')}>
                <td className={settingsTable.td}>
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center bg-muted"><TopicIcon name={t.icon} /></div>
                    <div className="min-w-0">
                      <div className={cn('font-medium', !t.enabled && 'text-muted-foreground')}>{t.plural_label}</div>
                      <div className="font-mono text-xs text-muted-foreground">{t.id}</div>
                    </div>
                  </div>
                </td>
                <td className={settingsTable.td}><GroupBadge group="Custom" /></td>
                <td className={cn(settingsTable.td, 'text-muted-foreground')}>{drafts.has(t.id) ? 'Draft' : SOURCE_LABEL[t.source]}</td>
                <td className={settingsTable.td} onClick={e => e.stopPropagation()}>
                  <EnabledSwitch
                    label={t.plural_label}
                    on={t.enabled}
                    busy={toggling === t.id}
                    disabled={!canEdit || drafts.has(t.id)}
                    onChange={() => void toggleEnabled(t)}
                  />
                </td>
              </tr>
            ))}

            {shownFeatures.map(({ scope, available, on }) => {
              return (
                <ScopeRow key={scope.id} icon={scope.icon} name={scope.label} id={scope.id} group="Workspace" type="Nexus feature"
                  description={available ? scope.description : `${scope.description} — the ${scope.label} feature is off in this workspace`}>
                  <EnabledSwitch label={scope.label} on={on} busy={toggling === scope.id}
                    disabled={!canEdit || !available} onChange={() => void toggleScope(scope.id, !on)} />
                </ScopeRow>
              );
            })}

            {shownEngines.map(({ engine, id, on }) => {
              return (
                <ScopeRow key={id} icon={engine.icon} name={engine.label} id={id} group="Web" type="Web engine" description={`${engine.description} — the query leaves Nexus`}>
                  <EnabledSwitch label={engine.label} on={on} busy={toggling === id}
                    disabled={!canEdit} onChange={() => void toggleScope(id, !on)} />
                </ScopeRow>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GroupBadge({ group }: { group: 'Custom' | 'Workspace' | 'Web' }) {
  return <Badge variant="outline">{group}</Badge>;
}

/** A feature or web-engine row: nothing to edit but whether search may use it. */
function ScopeRow({ icon, name, id, group, type, description, children }: {
  icon: string; name: string; id: string; group: 'Workspace' | 'Web'; type: string; description: string; children: React.ReactNode;
}) {
  return (
    <tr className={settingsTable.row}>
      <td className={settingsTable.td}>
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center bg-muted"><TopicIcon name={icon} /></div>
          <div className="min-w-0">
            <div className="font-medium">{name}</div>
            <div className="truncate text-xs text-muted-foreground" title={description}>{description}</div>
          </div>
        </div>
      </td>
      <td className={settingsTable.td}><GroupBadge group={group} /></td>
      <td className={cn(settingsTable.td, 'text-muted-foreground')}>{type}</td>
      <td className={settingsTable.td}><span className="sr-only">{id}</span>{children}</td>
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
  const [draft, setDraft] = useState<SearchTopic>(topic);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [testUri, setTestUri] = useState('');
  const confirm = useConfirm();
  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(topic), [draft, topic]);

  const set = <K extends keyof SearchTopic>(key: K, value: SearchTopic[K]) => setDraft(d => ({ ...d, [key]: value }));
  const setSection = (index: number, patch: Partial<TopicSection>) =>
    setDraft(d => ({ ...d, sections: d.sections.map((s, i) => (i === index ? { ...s, ...patch } : s)) }));
  const setRow = (index: number, patch: Partial<TopicResultRowDef>) =>
    setDraft(d => ({ ...d, result_rows: d.result_rows.map((r, i) => (i === index ? { ...r, ...patch } : r)) }));
  const moveRow = (index: number, delta: number) => setDraft(d => {
    const rows = [...d.result_rows];
    const [moved] = rows.splice(index, 1);
    rows.splice(Math.max(0, Math.min(rows.length, index + delta)), 0, moved!);
    return { ...d, result_rows: rows };
  });
  const moveSection = (index: number, delta: number) => setDraft(d => {
    const sections = [...d.sections];
    const [moved] = sections.splice(index, 1);
    sections.splice(Math.max(0, Math.min(sections.length, index + delta)), 0, moved!);
    return { ...d, sections };
  });

  const save = async () => {
    setSaving(true); setErrors([]);
    try {
      const saved = await topicsApi.save(workspaceId, draft);
      onSaved(saved); setSavedAt(Date.now());
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <TopicIcon name={draft.icon} size={18} />
          <h3 className="text-base font-semibold">{draft.plural_label}</h3>
          <Badge>{SOURCE_LABEL[topic.source]}</Badge>
          <a href={searchHref(workspaceId, { scope: topic.id })} className="inline-flex items-center gap-1 text-xs text-primary hover:underline"><Search size={12} /> Open in search</a>
        </div>
        {canEdit && (
          <div className="flex items-center gap-2">
            {topic.source !== 'builtin' && (
              <Button variant={topic.source === 'override' ? 'secondary' : 'destructive-ghost'} onClick={() => void reset()}>
                {topic.source === 'override' ? <><RotateCcw size={14} /> Reset</> : <><Trash2 size={14} /> Delete</>}
              </Button>
            )}
            <Button onClick={() => void save()} disabled={saving || (!dirty && !isDraft)}>
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save
            </Button>
          </div>
        )}
      </div>
      {savedAt && !dirty && <SettingsNotice tone="success"><span role="status">Saved.</span></SettingsNotice>}
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
        <Field label="Detail tab label" hint="The tab that shows one individual, after Results and Ontology (e.g. Resume, Card).">
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

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold">Result rows</h4>
          {canEdit && (
            <button type="button" onClick={() => set('result_rows', [...draft.result_rows, { id: `row_${draft.result_rows.length + 1}`, label: 'New row', query: ROW_QUERY_TEMPLATE }])}
              className={cn(buttonVariants({ variant: 'secondary', size: 'sm' }))}><Plus size={14} /> Add row</button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">Each row is one labelled line of metadata under every result. Several values are joined.</p>
        {draft.result_rows.length === 0 && <p className="text-sm text-muted-foreground">No rows: results show their title and subtitle only.</p>}
        {draft.result_rows.map((row, index) => (
          <div key={index} className="space-y-3 border border-border bg-card p-3">
            <fieldset disabled={disabled} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
              <Field label="Id"><input className={cn(input, 'font-mono text-xs')} value={row.id} onChange={e => setRow(index, { id: e.target.value })} /></Field>
              <Field label="Label"><input className={input} value={row.label} onChange={e => setRow(index, { label: e.target.value })} /></Field>
              <div className="flex items-end gap-1 pb-0.5">
                <IconButton label="Move up" onClick={() => moveRow(index, -1)} disabled={index === 0}><ChevronUp size={14} /></IconButton>
                <IconButton label="Move down" onClick={() => moveRow(index, 1)} disabled={index === draft.result_rows.length - 1}><ChevronDown size={14} /></IconButton>
                <IconButton label="Remove row" onClick={() => set('result_rows', draft.result_rows.filter((_, i) => i !== index))}><Trash2 size={14} /></IconButton>
              </div>
            </fieldset>
            <QueryEditor role="row" label="Query" contract={contract?.row} value={row.query} disabled={disabled}
              onChange={v => setRow(index, { query: v })} workspaceId={workspaceId} testUri={testUri} canEdit={canEdit} graphs={draft.graphs} />
          </div>
        ))}
      </div>

      <QueryEditor role="header" label="Detail header query" contract={contract?.header} value={draft.header_query} disabled={disabled}
        onChange={v => set('header_query', v)} workspaceId={workspaceId} testUri={testUri} canEdit={canEdit} graphs={draft.graphs} />

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

const IMAGE_QUERY_TEMPLATE = `PREFIX people: <http://ontology.naas.ai/people/>
SELECT ?uri ?image
WHERE {
  VALUES ?uri { {{ uris }} }
  ?uri people:hasPortrait ?p .
  ?p people:portrait_url ?image .
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
