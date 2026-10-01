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
import {
  blankTopic, searchHref,
  type PreviewResult, type QueryRole, type RoleContract, type SearchTopic, type TopicSection,
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
        <button type="button" onClick={() => select(null)} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft size={14} /> All topics
        </button>
        {loading && !selected ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 size={14} className="animate-spin" /> Loading…</p>
        ) : !selected ? (
          <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">There is no topic “{selectedId}” in this workspace.</p>
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
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Search</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">{topics.length + FEATURE_SCOPES.length + WEB_ENGINES.length}</span>
          </div>
          <p className="text-sm text-muted-foreground">
            What the search page of this workspace can look into. A disabled entry disappears from search for every
            member. Topics read every graph this workspace can read, unless a topic is limited to some of them.
          </p>
        </div>
        {canEdit && (
          <button onClick={() => void createTopic()} className="flex shrink-0 items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            <Plus size={16} /> New topic
          </button>
        )}
      </div>

      {error && <div role="alert" className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">{error}</div>}
      {tableError && <div role="alert" className="whitespace-pre-line rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">{tableError}</div>}
      {!canEdit && !loading && <p className="rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">Only workspace owners and admins can change search topics.</p>}

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
            <tr>
              <th className="p-3 font-medium">Name</th>
              <th className="p-3 font-medium">Group</th>
              <th className="p-3 font-medium">Type</th>
              <th className="p-3 text-right font-medium">Enabled</th>
            </tr>
          </thead>
          <tbody>
            {loading && !topics.length && (
              <tr><td colSpan={4} className="p-3 text-muted-foreground"><Loader2 size={14} className="mr-2 inline animate-spin" />Loading…</td></tr>
            )}
            {topics.map(t => (
              <tr key={t.id} onClick={() => select(t.id)} className="cursor-pointer border-b transition-colors last:border-0 hover:bg-muted/30">
                <td className="p-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted"><TopicIcon name={t.icon} /></div>
                    <div className="min-w-0">
                      <div className={cn('font-medium', !t.enabled && 'text-muted-foreground')}>{t.plural_label}</div>
                      <div className="font-mono text-xs text-muted-foreground">{t.id}</div>
                    </div>
                  </div>
                </td>
                <td className="p-3"><GroupBadge group="Custom" /></td>
                <td className="p-3 text-muted-foreground">{drafts.has(t.id) ? 'Draft' : SOURCE_LABEL[t.source]}</td>
                <td className="p-3 text-right" onClick={e => e.stopPropagation()}>
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

            {FEATURE_SCOPES.map(scope => {
              const available = featureOn(scope.feature);
              const on = available && !disabledScopes.includes(scope.id);
              return (
                <ScopeRow key={scope.id} icon={scope.icon} name={scope.label} id={scope.id} group="Workspace" type="Nexus feature"
                  description={available ? scope.description : `${scope.description} — the ${scope.label} feature is off in this workspace`}>
                  <EnabledSwitch label={scope.label} on={on} busy={toggling === scope.id}
                    disabled={!canEdit || !available} onChange={() => void toggleScope(scope.id, !on)} />
                </ScopeRow>
              );
            })}

            {WEB_ENGINES.map(engine => {
              const id = webEngineScopeId(engine.id);
              const on = !disabledScopes.includes(id);
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
  return <span className="bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">{group}</span>;
}

/** A feature or web-engine row: nothing to edit but whether search may use it. */
function ScopeRow({ icon, name, id, group, type, description, children }: {
  icon: string; name: string; id: string; group: 'Workspace' | 'Web'; type: string; description: string; children: React.ReactNode;
}) {
  return (
    <tr className="border-b last:border-0">
      <td className="p-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted"><TopicIcon name={icon} /></div>
          <div className="min-w-0">
            <div className="font-medium">{name}</div>
            <div className="truncate text-xs text-muted-foreground" title={description}>{description}</div>
          </div>
        </div>
      </td>
      <td className="p-3"><GroupBadge group={group} /></td>
      <td className="p-3 text-muted-foreground">{type}</td>
      <td className="p-3 text-right"><span className="sr-only">{id}</span>{children}</td>
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
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={`${label} enabled`}
      disabled={disabled || busy}
      onClick={onChange}
      className={cn('relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50',
        on ? 'bg-workspace-accent' : 'bg-muted-foreground/30')}
    >
      <span className={cn('absolute h-4 w-4 rounded-full bg-white shadow transition-all', on ? 'left-[18px]' : 'left-0.5')} />
      {busy && <Loader2 size={10} className="absolute left-1/2 -translate-x-1/2 animate-spin text-white" />}
    </button>
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
  const input = 'w-full rounded-md border bg-background px-2 py-1.5 text-sm outline-none focus:border-[color:var(--workspace-accent,#22c55e)] disabled:opacity-70';

  return (
    <div className="min-w-0 space-y-5">
      {confirm.dialog}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <TopicIcon name={draft.icon} size={18} />
          <h3 className="text-base font-semibold">{draft.plural_label}</h3>
          <span className="rounded-full bg-muted px-2 py-0.5 text-[10px]">{SOURCE_LABEL[topic.source]}</span>
          <a href={searchHref(workspaceId, { scope: topic.id })} className="inline-flex items-center gap-1 text-xs text-workspace-accent hover:underline"><Search size={12} /> Open in search</a>
        </div>
        {canEdit && (
          <div className="flex items-center gap-2">
            {topic.source !== 'builtin' && (
              <button onClick={() => void reset()} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground">
                {topic.source === 'override' ? <><RotateCcw size={14} /> Reset</> : <><Trash2 size={14} /> Delete</>}
              </button>
            )}
            <button onClick={() => void save()} disabled={saving || (!dirty && !isDraft)}
              className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save
            </button>
          </div>
        )}
      </div>
      {savedAt && !dirty && <p className="text-xs text-green-600" role="status">Saved.</p>}
      {errors.length > 0 && (
        <ul role="alert" className="list-disc space-y-0.5 rounded-lg border border-red-500/20 bg-red-500/10 p-3 pl-7 text-sm text-red-500">
          {errors.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      )}

      <fieldset disabled={disabled} className="grid gap-3 sm:grid-cols-2">
        <Field label="Label (singular)"><input className={input} value={draft.label} onChange={e => set('label', e.target.value)} /></Field>
        <Field label="Label (plural, tab name)"><input className={input} value={draft.plural_label} onChange={e => set('plural_label', e.target.value)} /></Field>
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
          <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={draft.enabled} onChange={e => set('enabled', e.target.checked)} /> Enabled</label>
        </div>
      </fieldset>

      <fieldset disabled={disabled} className="space-y-2">
        <legend className="mb-1 text-xs font-medium text-muted-foreground">Graphs</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" checked={draft.graphs.length === 0} onChange={() => set('graphs', [])} />
          All graphs this workspace can read <span className="text-xs text-muted-foreground">(default)</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" checked={draft.graphs.length > 0}
            onChange={() => { if (!draft.graphs.length && graphs?.length) set('graphs', [graphs[0]!.uri]); }}
            disabled={!graphs?.length} />
          Only these graphs
        </label>
        {draft.graphs.length > 0 && (
          <div className="ml-6 max-h-56 space-y-1 overflow-auto rounded-md border p-2">
            {(graphs || []).map(g => (
              <label key={g.uri} className="flex items-center gap-2 text-sm" title={g.uri}>
                <input
                  type="checkbox"
                  checked={draft.graphs.includes(g.uri)}
                  onChange={e => {
                    const next = e.target.checked ? [...draft.graphs, g.uri] : draft.graphs.filter(u => u !== g.uri);
                    if (next.length) set('graphs', next);
                  }}
                />
                <span className="truncate">{g.label}</span>
                <span className="truncate font-mono text-[10px] text-muted-foreground">{g.uri}</span>
              </label>
            ))}
            {draft.graphs.filter(u => !graphs?.some(g => g.uri === u)).map(u => (
              <p key={u} className="text-xs text-amber-600">{u} is not readable in this workspace: the topic skips it here.</p>
            ))}
          </div>
        )}
      </fieldset>

      <div className="rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground">
        <p className="mb-1 font-medium text-foreground">How queries are filled in</p>
        <p>
          <code>{'{{ q }}'}</code> is the text typed in the search box (write it inside quotes), <code>{'{{ uri }}'}</code> the selected
          individual as an IRI, <code>{'{{ limit }}'}</code>/<code>{'{{ offset }}'}</code> paging. Do not use <code>FROM</code>, <code>SERVICE</code> or a
          fixed <code>GRAPH</code>: queries read the graphs this workspace can read.
        </p>
        <label className="mt-2 flex items-center gap-2">
          <span className="shrink-0">Test individual</span>
          <input className={cn(input, 'font-mono text-xs')} value={testUri} onChange={e => setTestUri(e.target.value)} placeholder="IRI used by Test on header and section queries — Test the results query to pick one" />
        </label>
      </div>

      <QueryEditor role="results" label="Results query" contract={contract?.results} value={draft.results_query} disabled={disabled}
        onChange={v => set('results_query', v)} workspaceId={workspaceId} testUri={testUri} onPickUri={setTestUri} canEdit={canEdit} graphs={draft.graphs} />
      <QueryEditor role="header" label="Detail header query" contract={contract?.header} value={draft.header_query} disabled={disabled}
        onChange={v => set('header_query', v)} workspaceId={workspaceId} testUri={testUri} canEdit={canEdit} graphs={draft.graphs} />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold">Detail sections</h4>
          {canEdit && (
            <button type="button" onClick={() => set('sections', [...draft.sections, { id: `section_${draft.sections.length + 1}`, label: 'New section', empty_text: 'Nothing recorded.', link_topic: null, query: 'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nSELECT ?title ?item\nWHERE {\n  {{ uri }} ?p ?item .\n  ?item rdfs:label ?title .\n}\nLIMIT {{ limit }}' }])}
              className="flex items-center gap-1 text-xs text-workspace-accent hover:underline"><Plus size={12} /> Add section</button>
          )}
        </div>
        {draft.sections.length === 0 && <p className="text-sm text-muted-foreground">No sections: the detail shows the header only.</p>}
        {draft.sections.map((section, index) => (
          <div key={index} className="space-y-3 rounded-lg border p-3">
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

function QueryEditor({ role, label, contract, value, onChange, disabled, workspaceId, testUri, onPickUri, canEdit, graphs }: {
  role: QueryRole;
  label: string;
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
          <span className="text-[11px] text-muted-foreground">
            needs {contract.required.map(v => `?${v}`).join(' ')} · may use {contract.optional.map(v => `?${v}`).join(' ')}
            {contract.extra_as_facts && ' · other variables show as facts'}
          </span>
        )}
      </div>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        spellCheck={false}
        rows={Math.min(24, Math.max(6, value.split('\n').length + 1))}
        className="w-full rounded-md border bg-muted/30 p-2 font-mono text-xs leading-relaxed outline-none focus:border-[color:var(--workspace-accent,#22c55e)] disabled:opacity-80"
        aria-label={label}
      />
      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          {role === 'results' && (
            <input value={testQ} onChange={e => setTestQ(e.target.value)} placeholder="Test text for {{ q }} (empty lists all)"
              className="min-w-0 flex-1 rounded-md border bg-background px-2 py-1 text-xs outline-none" />
          )}
          <button type="button" onClick={() => void run()} disabled={running || (role !== 'results' && !testUri.trim())}
            title={role !== 'results' && !testUri.trim() ? 'Set a test individual first' : undefined}
            className="flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs font-medium hover:bg-secondary/80 disabled:opacity-50">
            {running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />} Test
          </button>
        </div>
      )}
      {error && <pre role="alert" className="whitespace-pre-wrap rounded-md border border-red-500/20 bg-red-500/10 p-2 text-xs text-red-500">{error}</pre>}
      {preview && (
        <div className="overflow-auto rounded-md border">
          <table className="w-full text-xs">
            <thead className="bg-muted/50">
              <tr>{columns.map(c => <th key={c} className={cn('px-2 py-1 text-left font-mono font-medium', slots.has(c) ? 'text-workspace-accent' : 'text-muted-foreground')}>?{c}</th>)}</tr>
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
                        {pick ? <button type="button" className="text-workspace-accent hover:underline" onClick={() => onPickUri(cell.value)} title="Use as test individual">{cell.value}</button> : cell?.value}
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
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-muted-foreground">{hint}</span>}
    </label>
  );
}

function IconButton({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} disabled={disabled}
      className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30">
      {children}
    </button>
  );
}
