'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Bookmark, Folder, Plus, Search, Trash2 } from 'lucide-react';
import { listViews, deleteView, type SavedView } from '@/lib/graph-query/client';
import { groupComposerViews } from '@/lib/graph-explorer';
import { useConfirm } from '@/components/ui/dialogs';
import './graph-explorer.css';

export function GraphComposerSidebar({ workspaceId }: { workspaceId: string }) {
  const [views, setViews] = useState<SavedView[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const request = useRef(0);
  const router = useRouter();
  const active = useSearchParams().get('view_id');
  const { confirm, dialog } = useConfirm();
  const root = `/workspace/${workspaceId}/graph/composer`;
  const refresh = useCallback(async () => {
    const generation = ++request.current;
    setLoading(true);
    setError('');
    try {
      const next = await listViews({ workspaceId, path: '', recursive: true });
      if (request.current === generation) setViews(next.filter((v) => v.kind === 'query'));
    } catch {
      if (request.current === generation) setError('Could not load saved views.');
    } finally {
      if (request.current === generation) setLoading(false);
    }
  }, [workspaceId]);
  useEffect(() => {
    const invalidate = () => {
      request.current++;
    };
    void refresh();
    const handler = () => void refresh();
    window.addEventListener('views-changed', handler);
    return () => {
      invalidate();
      window.removeEventListener('views-changed', handler);
    };
  }, [refresh]);
  async function remove(view: SavedView) {
    if (
      !(await confirm({
        title: `Delete view “${view.name || view.label}”?`,
        description: 'This removes the saved view and its query. This action cannot be undone.',
        confirmLabel: 'Delete View',
        destructive: true,
      }))
    )
      return;
    try {
      await deleteView(workspaceId, view.id);
      window.dispatchEvent(new Event('views-changed'));
      if (active === view.id) router.push(root);
    } catch {
      setError('Could not delete the saved view.');
    }
  }
  const groups = groupComposerViews(
    views.filter((v) =>
      `${v.name || v.label} ${v.path || ''}`.toLowerCase().includes(search.trim().toLowerCase()),
    ),
  );
  return (
    <div className="graph-explorer-sidebar">
      <label className="graph-explorer-search">
        <Search size={14} />
        <input
          aria-label="Search saved views"
          placeholder="Search views…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      <div className="graph-explorer-views-heading">
        <span>Views</span>
        <button
          type="button"
          title="New Composer view"
          aria-label="New Composer view"
          onClick={() => router.push(root)}
        >
          <Plus size={14} />
        </button>
      </div>
      {error && (
        <p className="graph-explorer-message" role="alert">
          {error} <button onClick={() => void refresh()}>Retry</button>
        </p>
      )}
      {loading ? (
        <p className="graph-explorer-message" role="status">
          Loading views…
        </p>
      ) : !groups.length ? (
        <p className="graph-explorer-message">
          {search ? 'No matching views.' : 'No saved views yet.'}
        </p>
      ) : (
        groups.map((group) => (
          <section className="graph-explorer-view-group" key={group.path}>
            {group.path && (
              <h3 title={group.path}>
                <Folder size={12} />
                {group.path}
              </h3>
            )}
            {group.views.map((view) => (
              <div className="graph-explorer-view-row" key={view.id}>
                <button
                  type="button"
                  aria-current={active === view.id ? 'page' : undefined}
                  onClick={() => router.push(`${root}?view_id=${encodeURIComponent(view.id)}`)}
                >
                  <Bookmark size={12} />
                  <span>{view.name || view.label}</span>
                </button>
                <button
                  type="button"
                  className="graph-explorer-view-delete"
                  aria-label={`Delete ${view.name || view.label}`}
                  onClick={() => void remove(view)}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </section>
        ))
      )}
      {dialog}
    </div>
  );
}
