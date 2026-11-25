'use client';

/** The middle pane: a service's header, path, search and its entries. */
import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react';
import {
  ChevronRight,
  CornerLeftUp,
  FileText,
  Folder,
  History,
  Keyboard,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud,
} from 'lucide-react';
import type { Failure } from './data-api';
import { childId, plural, type Crumb } from './data-model';
import type { ResourceEntry, ResourceServiceInfo } from './data-types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Notice } from '@/components/ui/notice';
import { SearchBox } from '@/components/ui/search-box';
import { Loading } from '@/components/ui/spinner';
import { CopyButton, Hint } from './data-ui';
import type { Column, Level, ServiceView } from './services/types';

function entryIcon(view: ServiceView, entry: ResourceEntry) {
  return view.entryIcon?.(entry) ?? (entry.kind === 'container' ? Folder : FileText);
}

/** The service's state and actions, under the page's title (which names the service). */
export function ServiceHeader({
  view,
  info,
  count,
  more,
  noun,
  onCreate,
  createBlocked,
  onRefresh,
  onRecent,
  onShortcuts,
}: {
  view: ServiceView;
  info: ResourceServiceInfo;
  count: number | null;
  more: boolean;
  noun: { one: string; many: string };
  onCreate?: () => void;
  createBlocked?: string | null;
  onRefresh: () => void;
  onRecent: () => void;
  onShortcuts: () => void;
}) {
  const caps = info.capabilities;
  return (
    <header className="data-service-header">
      <div className="data-service-heading">
        {view.readOnly && <Badge>Read-only</Badge>}
        {caps.reveal && <Badge variant="warning">Masked values</Badge>}
        {count !== null && (
          <span className="data-muted data-service-count">
            {plural(count, noun.one, noun.many)}
            {more ? '+' : ''}
          </span>
        )}
      </div>
      <div className="data-service-actions">
        <Button variant="secondary" size="sm" onClick={onRecent}>
          <History size={14} aria-hidden="true" /> Recent changes
        </Button>
        <Hint label="Keyboard shortcuts" shortcut="?">
          <Button variant="secondary" size="icon" aria-label="Keyboard shortcuts" onClick={onShortcuts}>
            <Keyboard size={14} aria-hidden="true" />
          </Button>
        </Hint>
        <Hint label="Refresh" shortcut="R">
          <Button variant="secondary" size="icon" aria-label="Refresh" onClick={onRefresh}>
            <RefreshCw size={14} aria-hidden="true" />
          </Button>
        </Hint>
        {!onCreate && createBlocked && (
          <Hint label={createBlocked}>
            <span className="data-disabled-wrap">
              <Button size="sm" disabled>
                <Plus size={14} aria-hidden="true" /> {view.createLabel ?? `New ${view.noun.one}`}
              </Button>
            </span>
          </Hint>
        )}
        {onCreate && (
          <Hint label={view.createLabel ?? `New ${view.noun.one}`} shortcut="N">
            <Button size="sm" onClick={onCreate}>
              <Plus size={14} aria-hidden="true" /> {view.createLabel ?? `New ${view.noun.one}`}
            </Button>
          </Hint>
        )}
      </div>
    </header>
  );
}

export function Toolbar({
  rootLabel,
  path,
  onCrumb,
  onUp,
  search,
  onSearch,
  searchRef,
  placeholder,
}: {
  rootLabel: string;
  path: Crumb[];
  onCrumb: (crumb: Crumb) => void;
  onUp: () => void;
  search: string;
  onSearch: (text: string) => void;
  searchRef: React.RefObject<HTMLInputElement | null>;
  placeholder: string;
}) {
  return (
    <div className="data-toolbar">
      {path.length > 1 && (
        <Hint label="Up one level" shortcut="⌫">
          <Button variant="ghost" size="icon" aria-label="Up one level" onClick={onUp}>
            <CornerLeftUp size={14} aria-hidden="true" />
          </Button>
        </Hint>
      )}
      <nav className="data-crumbs" aria-label="Path">
        {path.map((c, i) => {
          const label = i === 0 ? rootLabel : c.label;
          return (
            <span key={c.id || 'root'} className="data-crumb">
              {i > 0 && <ChevronRight size={12} aria-hidden="true" className="data-crumb-sep" />}
              {i === path.length - 1 ? (
                <span className="data-crumb-current" aria-current="location" title={c.id || undefined}>
                  {label}
                </span>
              ) : (
                <button type="button" className="data-crumb-link" onClick={() => onCrumb(c)} title={c.id || undefined}>
                  {label}
                </button>
              )}
            </span>
          );
        })}
      </nav>
      <SearchBox
        ref={searchRef}
        size="sm"
        className="data-search"
        placeholder={placeholder}
        label="Search"
        value={search}
        onChange={onSearch}
        onKeyDown={(e) => {
          if (e.key === 'Escape') e.currentTarget.blur();
        }}
      />
    </div>
  );
}

function NameCell({ view, entry }: { view: ServiceView; entry: ResourceEntry }) {
  const Icon = entryIcon(view, entry);
  const summary = view.summary ? view.summary(entry) : entry.attributes.summary;
  return (
    <span className="data-row-name">
      <span className={`data-row-icon${entry.kind === 'container' ? ' data-row-icon-container' : ''}`}>
        <Icon size={15} strokeWidth={1.75} aria-hidden="true" />
      </span>
      <span className="data-row-text">
        <span className="data-row-title">
          <span className="data-row-label" title={entry.id}>
            {view.title?.(entry) ?? entry.name}
          </span>
          {view.badges && <span className="data-row-badges">{view.badges(entry)}</span>}
        </span>
        {summary && <span className="data-row-summary">{summary}</span>}
      </span>
    </span>
  );
}

function RowActions({ entry, onDelete }: { entry: ResourceEntry; onDelete: (entry: ResourceEntry) => void }) {
  return (
    <span className="data-row-actions" onClick={(e) => e.stopPropagation()}>
      <CopyButton value={entry.id} label="Copy id" />
      {entry.kind === 'container' && entry.actions.includes('delete') && (
        <Button
          variant="destructive-ghost"
          size="icon"
          className="h-7 w-7"
          aria-label={`Delete ${entry.name}`}
          title={`Delete ${entry.name}`}
          onClick={() => onDelete(entry)}
        >
          <Trash2 size={14} aria-hidden="true" />
        </Button>
      )}
    </span>
  );
}

function ListLayout({
  view,
  columns,
  entries,
  selected,
  groupBy,
  onActivate,
  onDelete,
}: {
  view: ServiceView;
  columns: Column[];
  groupBy?: (entry: ResourceEntry) => string;
  entries: ResourceEntry[];
  selected: string | null;
  onActivate: (entry: ResourceEntry) => void;
  onDelete: (entry: ResourceEntry) => void;
}) {
  // The name always keeps room; extra columns scroll sideways in a narrow pane.
  const template = ['minmax(200px, 1fr)', ...columns.map((c) => c.width), '64px'].join(' ');
  return (
    <div className="data-list" role="listbox" aria-label="Entries" style={{ ['--data-cols' as string]: template }}>
      <div className="data-list-head" aria-hidden="true">
        <span>Name</span>
        {columns.map((c) => (
          <span key={c.id} className={c.align === 'end' ? 'data-align-end' : undefined}>
            {c.label}
          </span>
        ))}
        <span />
      </div>
      {entries.map((entry, i) => {
        const group = groupBy?.(entry);
        const newGroup = group !== undefined && (i === 0 || groupBy?.(entries[i - 1]) !== group);
        return (
          <Fragment key={entry.id}>
            {newGroup && (
              <div className="data-list-group" role="presentation">
                {group}
              </div>
            )}
            <div
              role="option"
              aria-selected={selected === entry.id}
              tabIndex={-1}
              data-entry={entry.id}
              className={`data-row${selected === entry.id ? ' data-row-selected' : ''}`}
              onClick={() => onActivate(entry)}
            >
              <NameCell view={view} entry={entry} />
              {columns.map((c) => (
                <span key={c.id} className={`data-row-cell${c.align === 'end' ? ' data-align-end' : ''}`}>
                  {c.render(entry)}
                </span>
              ))}
              <RowActions entry={entry} onDelete={onDelete} />
            </div>
          </Fragment>
        );
      })}
    </div>
  );
}

function CardsLayout({
  view,
  level,
  columns,
  entries,
  selected,
  onActivate,
  onDelete,
}: {
  view: ServiceView;
  level: Level;
  columns: Column[];
  entries: ResourceEntry[];
  selected: string | null;
  onActivate: (entry: ResourceEntry) => void;
  onDelete: (entry: ResourceEntry) => void;
}) {
  return (
    <div className="data-cards" role="listbox" aria-label="Entries">
      {entries.map((entry) => {
        const Icon = entryIcon(view, entry);
        const summary = view.summary ? view.summary(entry) : entry.attributes.summary;
        return (
          <div
            key={entry.id}
            role="option"
            aria-selected={selected === entry.id}
            tabIndex={-1}
            data-entry={entry.id}
            className={`data-card${selected === entry.id ? ' data-card-selected' : ''}`}
            onClick={() => onActivate(entry)}
          >
            <div className="data-card-head">
              <span className="data-card-icon">
                <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
              </span>
              <span className="data-card-title" title={entry.id}>
                {view.title?.(entry) ?? entry.name}
              </span>
              <RowActions entry={entry} onDelete={onDelete} />
            </div>
            {view.badges && <div className="data-card-badges">{view.badges(entry)}</div>}
            {level.card ? (
              <div className="data-card-body">{level.card(entry)}</div>
            ) : (
              summary && <p className="data-card-summary">{summary}</p>
            )}
            {columns.length > 0 && (
              <dl className="data-card-facts">
                {columns.map((c) => (
                  <div key={c.id}>
                    <dt>{c.label}</dt>
                    <dd>{c.render(entry)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        );
      })}
    </div>
  );
}

function LoadMore({ onVisible, loading }: { onVisible: () => void; loading: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver((items) => items[0]?.isIntersecting && onVisible(), {
      rootMargin: '240px',
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [onVisible]);
  return (
    <div ref={ref} className="data-load-more">
      <Button variant="secondary" size="sm" onClick={onVisible} disabled={loading}>
        {loading ? 'Loading…' : 'Load more'}
      </Button>
    </div>
  );
}

export function Browser({
  view,
  level,
  entries,
  failure,
  listable,
  parent,
  search,
  selected,
  hasMore,
  loadingMore,
  canCreate,
  onActivate,
  onDelete,
  onLookup,
  onLoadMore,
  onCreate,
  onDrop,
}: {
  view: ServiceView;
  level: Level;
  entries: ResourceEntry[] | null;
  failure: Failure | null;
  listable: boolean;
  parent: string;
  search: string;
  selected: string | null;
  hasMore: boolean;
  loadingMore: boolean;
  canCreate: boolean;
  onActivate: (entry: ResourceEntry) => void;
  onDelete: (entry: ResourceEntry) => void;
  onLookup: (id: string) => void;
  onLoadMore: () => void;
  onCreate?: () => void;
  onDrop?: (files: File[]) => void;
}) {
  const [lookup, setLookup] = useState('');
  const [dragging, setDragging] = useState(false);
  const columns = level.columns ?? [];
  const dropTarget = onDrop && canCreate;

  let body: ReactNode;
  if (entries === null) body = <Loading />;
  else if (entries.length === 0 && failure === null && listable) {
    body = search ? (
      <EmptyState
        icon={<Search size={22} strokeWidth={1.5} />}
        title="No matches"
        description={`Nothing loaded matches “${search}”.${hasMore ? ' Load more entries to search further.' : ''}`}
      />
    ) : (
      <EmptyState
        icon={<view.icon size={22} strokeWidth={1.5} />}
        title={level.emptyTitle ?? `No ${(level.noun ?? view.noun).many} yet`}
        description={level.emptyText}
        action={
          onCreate && (
            <Button size="sm" onClick={onCreate}>
              <Plus size={14} aria-hidden="true" /> {view.createLabel ?? `New ${view.noun.one}`}
            </Button>
          )
        }
      />
    );
  } else if (entries.length === 0) body = null;
  else if (level.layout === 'cards') {
    body = (
      <CardsLayout
        view={view}
        level={level}
        columns={columns}
        entries={entries}
        selected={selected}
        onActivate={onActivate}
        onDelete={onDelete}
      />
    );
  } else {
    body = (
      <ListLayout
        view={view}
        columns={columns}
        entries={entries}
        selected={selected}
        groupBy={level.groupBy}
        onActivate={onActivate}
        onDelete={onDelete}
      />
    );
  }

  return (
    <div
      className={`data-browser${dragging ? ' data-browser-dragging' : ''}`}
      onDragOver={(e) => {
        if (!dropTarget || !e.dataTransfer.types.includes('Files')) return;
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
        setDragging(false);
      }}
      onDrop={(e) => {
        if (!dropTarget) return;
        e.preventDefault();
        setDragging(false);
        const files = Array.from(e.dataTransfer.files);
        if (files.length) onDrop?.(files);
      }}
    >
      {failure && (
        <Notice tone="error" className="data-level-notice">
          {failure.source === 'audit' ? 'Audit log: ' : ''}
          {failure.reason}
        </Notice>
      )}
      {level.notice && <div className="data-level-notice">{level.notice}</div>}
      {!listable && (
        <form
          className="data-lookup"
          onSubmit={(e) => {
            e.preventDefault();
            if (lookup.trim()) onLookup(childId(parent, lookup));
          }}
        >
          <p className="data-lookup-text">
            This service cannot list these {(level.noun ?? view.noun).many}. Open one by its id.
          </p>
          <div className="data-lookup-row">
            <Input
              aria-label="Id to open"
              placeholder="Id"
              value={lookup}
              onChange={(e) => setLookup(e.target.value)}
              autoComplete="off"
              spellCheck={false}
            />
            <Button type="submit" variant="secondary" disabled={!lookup.trim()}>
              Open
            </Button>
          </div>
        </form>
      )}
      {body}
      {entries !== null && hasMore && <LoadMore onVisible={onLoadMore} loading={loadingMore} />}
      {dragging && (
        <div className="data-drop-overlay" aria-hidden="true">
          <UploadCloud size={28} />
          <p>Drop to upload here</p>
        </div>
      )}
    </div>
  );
}
