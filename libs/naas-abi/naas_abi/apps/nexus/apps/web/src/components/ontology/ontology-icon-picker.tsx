'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Check, Loader2, Search, X } from 'lucide-react';
import { useWorkspaceStore } from '@/stores/workspace';
import { useOntologyIconsStore } from '@/stores/ontology-icons';
import { ontologyTopicIcon, type OntologyTopicSubject } from '@/lib/ontology-topic-icon';
import { cachedIconPaths, iconLabel, iconTarget, iconTargetKey, ICON_PREFIX, loadIconCatalog, loadIconPaths, pickerPosition, searchIconNames, SUGGESTED_ICONS } from '@/lib/ontology-icon-library';
import { OntologyTopicIcon } from './ontology-topic-icon';
import './ontology-icon-picker.css';

const PAGE_SIZE = 48;
export function OntologyIconPicker({ subject, className = '' }: { subject: OntologyTopicSubject; className?: string }) {
  const workspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const target = iconTarget(subject);
  if (!workspaceId || !target) return <OntologyTopicIcon subject={subject} className={className} />;
  return <IconPickerSession key={`${workspaceId}:${iconTargetKey(target)}`} subject={subject} className={className} workspaceId={workspaceId} />;
}

function IconPickerSession({ subject, className, workspaceId }: { subject: OntologyTopicSubject; className: string; workspaceId: string }) {
  const store = useOntologyIconsStore();
  const target = iconTarget(subject)!;
  const key = iconTargetKey(target);
  const ready = store.workspaceId === workspaceId && !store.loading;
  const override = store.workspaceId === workspaceId ? store.icons[key] : undefined;
  const chosen = override?.slice(ICON_PREFIX.length) || ontologyTopicIcon(subject);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [catalog, setCatalog] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assetError, setAssetError] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [retry, setRetry] = useState(0);
  const [, renderPaths] = useState(0);
  const [position, setPosition] = useState({ left: 12, top: 12, width: 360, maxHeight: 480 });
  const trigger = useRef<HTMLButtonElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const grid = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const results = useMemo(() => searchIconNames(catalog || SUGGESTED_ICONS, query), [catalog, query]);
  const names = useMemo(() => results.slice(0, limit), [results, limit]);

  useEffect(() => { if (body.current) body.current.scrollTop = 0; }, [query, catalog]);

  useLayoutEffect(() => {
    if (!open) return;
    const update = () => { if (trigger.current) setPosition(pickerPosition(trigger.current.getBoundingClientRect(), { width: window.innerWidth, height: window.innerHeight })); };
    update(); window.addEventListener('resize', update); window.addEventListener('scroll', update, true);
    return () => { window.removeEventListener('resize', update); window.removeEventListener('scroll', update, true); };
  }, [open]);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setAssetError(null);
    void loadIconPaths(names).then(() => { if (active) renderPaths(value => value + 1); }).catch(() => { if (active) setAssetError('Could not load these icons.'); });
    return () => { active = false; };
  }, [open, names, retry]);
  async function browseLibrary() {
    setLoading(true); setError(null);
    try { const data = await loadIconCatalog(); setCatalog(data.names); }
    catch { setError('Could not load the icon library. Try again.'); }
    finally { setLoading(false); }
  }
  async function save(name: string | null) {
    setSaving(true); setError(null);
    try {
      await store.save(workspaceId, target, name ? ICON_PREFIX + name : null);
      setOpen(false);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not save the icon.'); }
    finally { setSaving(false); }
  }
  function moveInGrid(event: KeyboardEvent<HTMLDivElement>) {
    const buttons = Array.from(grid.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') || []);
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (index < 0) return;
    const next = { ArrowRight: index + 1, ArrowLeft: index - 1, ArrowDown: index + 8, ArrowUp: index - 8, Home: 0, End: buttons.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault(); event.stopPropagation(); buttons[Math.max(0, Math.min(buttons.length - 1, next))]?.focus();
  }
  const disabled = ready && !store.error && !store.canEdit;
  return <div className={`ontology-icon-control ${className}`}>
    <Dialog.Root open={open} onOpenChange={value => {
      if (saving) return;
      setOpen(value);
      if (value) { setError(null); if (!ready || store.error) void store.load(workspaceId, true); }
    }}>
      <Dialog.Trigger asChild><button ref={trigger} type="button" className="ontology-icon-trigger" disabled={disabled} aria-label={`Change icon for ${subject.name}`} title={disabled ? 'Your workspace role cannot change this icon' : 'Change icon'}>
        <OntologyTopicIcon subject={subject} /><span className="ontology-icon-trigger-hint">Change icon</span>
      </button></Dialog.Trigger>
      <Dialog.Portal><Dialog.Overlay className="ontology-icon-picker-overlay" /><Dialog.Content className="ontology-icon-picker" style={position} onOpenAutoFocus={event => { event.preventDefault(); search.current?.focus(); }} onEscapeKeyDown={event => { if (saving) event.preventDefault(); }}>
        <header><div><Dialog.Title>Change icon</Dialog.Title><Dialog.Description>Material Symbols Light · shared with this workspace</Dialog.Description></div><Dialog.Close className="ontology-icon-picker-close" disabled={saving} aria-label="Close icon picker"><X size={15} /></Dialog.Close></header>
        <label className="ontology-icon-picker-search"><Search size={15} /><input ref={search} value={query} placeholder="Search icons…" aria-label="Search icons" onChange={event => {
          setQuery(event.target.value); setLimit(PAGE_SIZE); if (!catalog && !loading && event.target.value.trim()) void browseLibrary();
        }} onKeyDown={event => { if (event.key === 'ArrowDown') { event.preventDefault(); grid.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus(); } }} /></label>
        <div className="ontology-icon-picker-results-label"><span>{catalog ? `${results.length.toLocaleString()} icons` : 'Suggested icons'}</span>{loading && <Loader2 size={13} className="animate-spin" />}</div>
        <div ref={body} className="ontology-icon-picker-body">
          {(!ready || store.loading) && <p role="status">Loading workspace icons…</p>}
          {store.error && <p role="alert">{store.error} <button type="button" onClick={() => void store.load(workspaceId, true)}>Retry</button></p>}
          {error && <p role="alert">{error}</p>}
          {assetError && <p role="alert">{assetError} <button type="button" onClick={() => setRetry(value => value + 1)}>Retry</button></p>}
          <div ref={grid} className="ontology-icon-picker-grid" aria-label="Icon choices" onKeyDown={moveInGrid}>
            {names.map(name => { const paths = cachedIconPaths(name); return <button key={name} type="button" aria-label={iconLabel(name)} title={iconLabel(name)} aria-pressed={name === chosen}
              disabled={saving || !ready || !store.canEdit || !!store.error || !paths} onClick={() => void save(name)}>
              {paths ? <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">{paths.map((path, index) => <path key={index} d={path} />)}</svg> : <span className="ontology-icon-picker-placeholder" />}
              {name === chosen && <Check size={10} className="ontology-icon-picker-check" />}
            </button>; })}
          </div>
          {!names.length && !loading && <p>No icons match “{query}”.</p>}
          {!catalog && <button type="button" className="ontology-icon-picker-more" disabled={loading} onClick={() => void browseLibrary()}>{loading ? 'Loading library…' : 'Browse full library'}</button>}
          {catalog && results.length > limit && <button type="button" className="ontology-icon-picker-more" onClick={() => setLimit(value => value + PAGE_SIZE)}>Load more ({Math.min(limit, results.length)} of {results.length.toLocaleString()})</button>}
        </div>
        <footer><button type="button" disabled={saving || !override || !ready || !store.canEdit || !!store.error} onClick={() => void save(null)}>Reset to suggested</button>{saving && <span role="status">Saving…</span>}</footer>
      </Dialog.Content></Dialog.Portal>
    </Dialog.Root>
  </div>;
}
