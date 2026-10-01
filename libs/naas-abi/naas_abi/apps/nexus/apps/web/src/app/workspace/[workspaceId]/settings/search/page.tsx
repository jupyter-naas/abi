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
import { ChevronDown, ChevronUp, Loader2, Play, Plus, RotateCcw, Save, Search, Trash2 } from 'lucide-react';
import { TopicIcon, TOPIC_ICONS } from '@/components/search/topic-icon';
import { useConfirm, usePrompt } from '@/components/ui/dialogs';
import { cn } from '@/lib/utils';
import {
  blankTopic, searchHref,
  type PreviewResult, type QueryRole, type RoleContract, type SearchTopic, type TopicSection,
} from '@/lib/search-topics';
import { TopicApiError, topicsApi } from '@/lib/search-topics-api';
import { useSearchTopicsStore } from '@/stores/search-topics';

const SOURCE_LABEL: Record<SearchTopic['source'], string> = { builtin: 'Built-in', override: 'Customized', custom: 'Custom' };

export default function SearchSettingsPage() {
  return <Suspense fallback={null}><SearchSettings /></Suspense>;
}

function SearchSettings() {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const selectedId = useSearchParams()?.get('topic');
  const { topics, canEdit, loading, error, load, replace, remove } = useSearchTopicsStore();
  const [contract, setContract] = useState<Record<QueryRole, RoleContract> | null>(null);
  const prompt = usePrompt();
  // Topics created here and not saved yet exist only in the browser.
  const [drafts, setDrafts] = useState<Set<string>>(new Set());

  useEffect(() => { if (workspaceId) void load(workspaceId, true); }, [workspaceId, load]);
  useEffect(() => { topicsApi.contract().then(setContract).catch(() => setContract(null)); }, []);

  const selected = topics.find(t => t.id === selectedId) || topics[0] || null;
  const select = (id: string) => router.replace(`/workspace/${encodeURIComponent(workspaceId)}/settings/search?topic=${encodeURIComponent(id)}`, { scroll: false });

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

  return (
    <div className="space-y-6">
      {prompt.dialog}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Search topics</h2>
          <p className="text-sm text-muted-foreground">
            Each topic is a tab of the search page. Its SPARQL queries run on the graphs this workspace can read;
            their variables fill the results list, the detail header and the detail sections.
          </p>
        </div>
        {canEdit && (
          <button onClick={() => void createTopic()} className="flex shrink-0 items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            <Plus size={16} /> New topic
          </button>
        )}
      </div>

      {error && <div role="alert" className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">{error}</div>}
      {!canEdit && !loading && <p className="rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">Only workspace owners and admins can change search topics.</p>}

      <div className="grid gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
        <ul className="space-y-1" aria-label="Topics">
          {loading && !topics.length && <li className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 size={14} className="animate-spin" /> Loading…</li>}
          {topics.map(t => (
            <li key={t.id}>
              <button
                onClick={() => select(t.id)}
                aria-current={selected?.id === t.id ? 'true' : undefined}
                className={cn('flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-muted', selected?.id === t.id && 'bg-workspace-accent-10 text-workspace-accent')}
              >
                <TopicIcon name={t.icon} />
                <span className={cn('flex-1 truncate', !t.enabled && 'text-muted-foreground line-through')}>{t.plural_label}</span>
                <span className="text-[10px] text-muted-foreground">{SOURCE_LABEL[t.source]}</span>
              </button>
            </li>
          ))}
        </ul>

        {selected && (
          <TopicEditor
            key={`${selected.id}:${selected.source}`}
            workspaceId={workspaceId}
            topic={selected}
            topics={topics}
            contract={contract}
            canEdit={canEdit}
            isDraft={drafts.has(selected.id)}
            onSaved={(saved) => { replace(saved); setDrafts(d => { const n = new Set(d); n.delete(saved.id); return n; }); }}
            onReset={(restored) => { if (restored) replace(restored); else { remove(selected.id); select(topics.find(t => t.id !== selected.id)?.id || ''); } }}
            onDiscardNew={() => { remove(selected.id); setDrafts(d => { const n = new Set(d); n.delete(selected.id); return n; }); }}
          />
        )}
      </div>
    </div>
  );
}

function TopicEditor({ workspaceId, topic, topics, contract, canEdit, isDraft, onSaved, onReset, onDiscardNew }: {
  workspaceId: string;
  topic: SearchTopic;
  topics: SearchTopic[];
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
        onChange={v => set('results_query', v)} workspaceId={workspaceId} testUri={testUri} onPickUri={setTestUri} canEdit={canEdit} />
      <QueryEditor role="header" label="Detail header query" contract={contract?.header} value={draft.header_query} disabled={disabled}
        onChange={v => set('header_query', v)} workspaceId={workspaceId} testUri={testUri} canEdit={canEdit} />

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
              onChange={v => setSection(index, { query: v })} workspaceId={workspaceId} testUri={testUri} canEdit={canEdit} />
          </div>
        ))}
      </div>
    </div>
  );
}

function QueryEditor({ role, label, contract, value, onChange, disabled, workspaceId, testUri, onPickUri, canEdit }: {
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
}) {
  const [testQ, setTestQ] = useState('');
  const [running, setRunning] = useState(false);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setRunning(true); setError(null);
    try {
      const params: Record<string, string> = role === 'results' ? { q: testQ } : { uri: testUri.trim() };
      setPreview(await topicsApi.preview(workspaceId, role, value, params));
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
