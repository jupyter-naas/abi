'use client';

/**
 * The Data tab: every kernel service's data, browsable and editable by platform
 * super admins. Service-specific rendering lives in ``services/``; changes are
 * confirmed by typing the id and audited by the API before they happen.
 */
import './data.css';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import * as Tooltip from '@radix-ui/react-tooltip';
import { Database } from 'lucide-react';
import { createDataApi, type DataApi, type Failure } from './data-api';
import { childId, decodeLocation, encodeLocation, plural } from './data-model';
import type { ResourceEntry } from './data-types';
import { EmptyState, Notice } from './data-ui';
import { CreateDialog, DeleteDialog, EditorDialog, type EditorRequest } from './dialogs';
import { Inspector } from './inspector';
import { RecentChanges } from './recent';
import { ShortcutsSheet } from './shortcuts';
import { ServiceRail } from './rail';
import { Browser, ServiceHeader, Toolbar } from './browser';
import { viewFor } from './services/registry';
import { ToastStack, useToasts } from './toasts';
import { useExplorer } from './use-explorer';

const WIDTH_KEY = 'nexus-data-inspector-width';
const MIN_WIDTH = 340;
const MAX_WIDTH = 860;

/** The width the user chose, or null to use the service's default. */
function readWidth(): number | null {
  try {
    const stored = Number(window.localStorage.getItem(WIDTH_KEY));
    if (stored >= MIN_WIDTH && stored <= MAX_WIDTH) return stored;
  } catch {
    // Storage may be unavailable (private mode): use the default.
  }
  return null;
}

function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const el = target;
  return (
    el.isContentEditable ||
    ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) ||
    Boolean(el.closest('.monaco-editor, [role="dialog"]'))
  );
}

export function DataExplorer({
  api: injected,
  nonce = 0,
  save = saveBlob,
}: {
  api?: DataApi;
  nonce?: number;
  save?: (blob: Blob, name: string) => void;
}) {
  const api = useMemo(() => injected ?? createDataApi(), [injected]);
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const initial = useMemo(() => decodeLocation(new URLSearchParams(params.toString())), []); // eslint-disable-line react-hooks/exhaustive-deps
  const x = useExplorer(api, initial, nonce);
  const { toasts, push, dismiss } = useToasts();
  const searchRef = useRef<HTMLInputElement>(null);
  const [chosenWidth, setWidth] = useState<number | null>(null);
  const [editor, setEditor] = useState<EditorRequest | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<ResourceEntry | null>(null);
  const [recent, setRecent] = useState(false);
  const [shortcuts, setShortcuts] = useState(false);

  useEffect(() => setWidth(readWidth()), []);
  const resize = useCallback((next: number) => {
    const clamped = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, next));
    setWidth(clamped);
    try {
      window.localStorage.setItem(WIDTH_KEY, String(clamped));
    } catch {
      // Not persisted: fine.
    }
  }, []);

  const view = x.service ? viewFor(x.service.name) : null;
  const depth = x.path.length - 1;
  const level = useMemo(
    () => (view?.level ? view.level(depth, x.parent, x.entries ?? undefined) : {}),
    [view, depth, x.parent, x.entries],
  );
  const noun = level.noun ?? view?.noun ?? { one: 'entry', many: 'entries' };
  const createHere = view?.canCreate?.(depth, x.parent) ?? true;
  const createBlocked = typeof createHere === 'string' ? createHere : null;
  const canCreate = Boolean(x.service?.capabilities.create) && createHere === true;
  const parentLabel = x.path.length > 1 ? x.path[x.path.length - 1].label : (view?.label ?? '');
  const itemId = x.detail?.entry.id ?? null;

  // Keep the location in the URL so a refresh or a shared link lands in the same place.
  useEffect(() => {
    const next = encodeLocation({ service: x.service?.name ?? null, path: x.path, item: itemId }, new URLSearchParams(params.toString()));
    if (next.toString() !== params.toString()) router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }, [x.service?.name, x.path, itemId]); // eslint-disable-line react-hooks/exhaustive-deps

  const notify = useCallback(
    (failure: Failure) => push({ tone: 'danger', title: failure.source === 'audit' ? 'Audit log unavailable' : 'Something went wrong', detail: failure.reason }),
    [push],
  );

  const activate = (entry: ResourceEntry) => {
    if (entry.kind === 'container') x.open({ id: entry.id, label: entry.name });
    else void x.openItem(entry.id);
  };

  const startCreate = () => {
    if (!view || !canCreate) return;
    if (view.create) setCreating(true);
    else setEditor({ mode: 'create', parent: x.parent, parentLabel, initial: view.editor?.template?.(x.parent) ?? '' });
  };

  const startEdit = async () => {
    if (!x.detail || !x.detail.entry.actions.includes('write')) return;
    let initial = '';
    const content = x.detail.content;
    if (content?.encoding === 'text' && !content.truncated) initial = content.text ?? '';
    else if (content?.encoding === 'masked' || content?.truncated) {
      const full = await x.download(x.detail.entry.id);
      if (full.ok) initial = await full.data.text();
    }
    setEditor({ mode: 'edit', parent: x.parent, parentLabel, entry: x.detail.entry, initial });
  };

  const download = async (id: string, name: string) => {
    const result = await x.download(id);
    if (result.ok) save(result.data, name);
    else notify(result);
  };

  const upload = async (files: File[]) => {
    let done = 0;
    for (const file of files) {
      const name = view?.dropName ? view.dropName(file) : file.name;
      if (!name) {
        push({ tone: 'danger', title: `${file.name} was not uploaded`, detail: view?.dropHint });
        continue;
      }
      const result = await x.write(childId(x.parent, name), file);
      if (result.ok) done += 1;
      else if (result.status === 409) push({ tone: 'danger', title: `${file.name} already exists`, detail: 'Open it and use Edit to replace it.' });
      else notify(result);
    }
    if (done) push({ tone: 'success', title: `Uploaded ${plural(done, 'file', 'files')}`, detail: `to ${parentLabel}` });
  };

  // Keyboard: / search · j k ↑ ↓ move · Enter open · Esc close · ⌫ up · n new · e edit · d download · r refresh · ⌘⌫ delete
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (typing(event.target) || editor || creating || deleting || recent || shortcuts) return;
      const list = x.entries ?? [];
      const index = list.findIndex((e) => e.id === x.selected);
      const move = (step: number) => {
        if (!list.length) return;
        const next = list[Math.min(list.length - 1, Math.max(0, index + step))];
        x.select(next.id);
        document.querySelector<HTMLElement>(`[data-entry="${CSS.escape(next.id)}"]`)?.scrollIntoView?.({ block: 'nearest' });
        if (next.kind === 'item' && x.detail) void x.openItem(next.id);
      };
      if (event.key === '?') {
        setShortcuts(true);
      } else if (event.key === '/') {
        event.preventDefault();
        searchRef.current?.focus();
      } else if (event.key === 'ArrowDown' || event.key === 'j') {
        event.preventDefault();
        move(index < 0 ? 0 : 1);
      } else if (event.key === 'ArrowUp' || event.key === 'k') {
        event.preventDefault();
        move(-1);
      } else if (event.key === 'Enter' && index >= 0) {
        activate(list[index]);
      } else if (event.key === 'Escape') {
        if (x.detail || x.detailFailure) x.closeItem();
        else x.select(null);
      } else if (event.key === 'Backspace' && (event.metaKey || event.ctrlKey)) {
        if (x.detail?.entry.actions.includes('delete')) setDeleting(x.detail.entry);
      } else if (event.key === 'Backspace') {
        x.up();
      } else if (event.key === 'n' && canCreate) {
        startCreate();
      } else if (event.key === 'e' && x.detail) {
        void startEdit();
      } else if (event.key === 'd' && x.detail?.entry.actions.includes('download')) {
        void download(x.detail.entry.id, x.detail.entry.name);
      } else if (event.key === 'r') {
        x.refresh();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  if (x.servicesFailure) {
    return (
      <div className="data-explorer-state">
        <Notice tone="danger">{x.servicesFailure.reason}</Notice>
      </div>
    );
  }
  if (!x.services) {
    return <div className="data-explorer-state data-muted">Loading services…</div>;
  }

  const showInspector = Boolean(x.detail || x.detailLoading || x.detailFailure);

  return (
    <Tooltip.Provider>
      <div className="data-explorer">
        <ServiceRail
          services={x.services}
          active={x.service?.name ?? null}
          onSelect={x.selectService}
          onRecent={() => setRecent(true)}
          onShortcuts={() => setShortcuts(true)}
        />
        <section className="data-main" data-service={x.service?.name} aria-label={view?.label ?? 'Data'}>
          {x.service && view ? (
            <>
              <ServiceHeader
                view={view}
                info={x.service}
                count={x.entries ? x.loadedCount : null}
                more={x.hasMore}
                noun={noun}
                onCreate={canCreate ? startCreate : undefined}
                createBlocked={x.service.capabilities.create ? createBlocked : null}
                onRefresh={x.refresh}
              />
              <Toolbar
                rootLabel={view.label}
                path={x.path}
                onCrumb={x.open}
                onUp={x.up}
                search={x.search}
                onSearch={x.setSearch}
                searchRef={searchRef}
                placeholder={x.service.capabilities.search ? `Search ${noun.many}` : `Filter ${noun.many}`}
              />
              <Browser
                view={view}
                level={level}
                entries={x.entries}
                failure={x.listFailure}
                listable={x.listable}
                parent={x.parent}
                search={x.search}
                selected={x.selected}
                hasMore={x.hasMore}
                loadingMore={x.loadingMore}
                canCreate={canCreate}
                onActivate={activate}
                onDelete={setDeleting}
                onLookup={(id) => void x.openItem(id)}
                onLoadMore={x.loadMore}
                onCreate={canCreate ? startCreate : undefined}
                onDrop={view.acceptsDrops ? (files) => void upload(files) : undefined}
              />
            </>
          ) : (
            <EmptyState icon={Database} title="No service data is reachable from this API" />
          )}
        </section>
        {showInspector && view && (
          <Inspector
            view={view}
            detail={x.detail}
            loading={x.detailLoading}
            failure={x.detailFailure}
            revealedUntil={x.revealedUntil}
            revealing={x.revealing}
            width={chosenWidth ?? view.inspectorWidth ?? 460}
            onResize={resize}
            onClose={x.closeItem}
            onReveal={async () => {
              const failure = await x.reveal(view.revealSeconds ?? 30);
              if (failure) notify(failure);
            }}
            onHide={x.hide}
            onDownload={() => x.detail && void download(x.detail.entry.id, x.detail.entry.name)}
            onEdit={() => void startEdit()}
            onDelete={() => x.detail && setDeleting(x.detail.entry)}
            loadHistory={() => x.history(x.detail?.entry.id ?? '')}
            previewContext={{
              download: async () => {
                if (!x.detail) return null;
                const result = await x.download(x.detail.entry.id);
                return result.ok ? result.data : null;
              },
              reveal: async () => {
                const failure = await x.reveal(view.revealSeconds ?? 30);
                if (failure) notify(failure);
              },
              revealing: x.revealing,
              open: (id) => void x.openItem(id),
            }}
          />
        )}
        {editor && view && x.service && (
          <EditorDialog
            request={editor}
            view={view}
            writeFormat={x.service.capabilities.write_format}
            onClose={() => setEditor(null)}
            onSave={async (id, body, confirm) => {
              const result = await x.write(id, body, confirm);
              if (result.ok) {
                setEditor(null);
                push({ tone: 'success', title: editor.mode === 'edit' ? 'Saved' : `Created ${result.data.name}`, detail: 'Recorded in the audit log' });
              }
              return result;
            }}
          />
        )}
        {creating && view && (
          <CreateDialog
            view={view}
            parent={x.parent}
            parentLabel={parentLabel}
            onClose={() => setCreating(false)}
            onSave={async (id, body) => {
              const result = await x.write(id, body);
              if (result.ok) {
                setCreating(false);
                push({ tone: 'success', title: `${view.createLabel ?? 'Created'}: ${result.data.name}`, detail: 'Recorded in the audit log' });
              }
              return result;
            }}
          />
        )}
        {deleting && view && (
          <DeleteDialog
            entry={deleting}
            noun={(view.nounFor?.(deleting, depth) ?? (deleting.kind === 'container' ? { one: 'container', many: 'containers' } : view.noun)).one}
            verb={view.deleteLabel}
            warning={view.deleteWarning?.(deleting)}
            onClose={() => setDeleting(null)}
            onConfirm={async (typed) => {
              const result = await x.remove(deleting.id, typed);
              if (!result.ok) return result;
              push({
                tone: 'success',
                title: `${view.deleteLabel ? `${view.deleteLabel}ed` : 'Deleted'} ${deleting.name}`,
                detail: 'Recorded in the audit log',
              });
              setDeleting(null);
              return null;
            }}
          />
        )}
        {recent && (
          <RecentChanges
            api={api}
            onClose={() => setRecent(false)}
            onOpen={(service, id) => {
              setRecent(false);
              x.goTo(service, id);
            }}
          />
        )}
        {shortcuts && <ShortcutsSheet onClose={() => setShortcuts(false)} />}
        <ToastStack toasts={toasts} dismiss={dismiss} />
      </div>
    </Tooltip.Provider>
  );
}
