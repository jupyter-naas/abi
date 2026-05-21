'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { Network, Search, Waypoints, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useGraphConfigsStore } from '@/stores/graph-configs';

export default function GraphsSettingsPage() {
  const params = useParams();
  const workspaceId = params?.workspaceId as string | undefined;
  const [mounted, setMounted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const { graphs, loading, fetchGraphs, toggleGraph } = useGraphConfigsStore();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!workspaceId) return;
    void fetchGraphs(workspaceId);
  }, [workspaceId, fetchGraphs]);

  const filteredGraphs = useMemo(() => {
    const list = graphs
      .slice()
      .sort((a, b) =>
        a.role_label.localeCompare(b.role_label) || a.label.localeCompare(b.label)
      );
    if (!searchQuery.trim()) return list;
    const q = searchQuery.toLowerCase();
    return list.filter(
      (g) =>
        g.label.toLowerCase().includes(q) ||
        g.uri.toLowerCase().includes(q) ||
        g.role_label.toLowerCase().includes(q)
    );
  }, [graphs, searchQuery]);

  if (!mounted) {
    return (
      <div className="flex items-center justify-center p-8">
        <p className="text-muted-foreground">Loading graphs...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Graphs</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {filteredGraphs.length}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Enable or disable the named graphs available in this workspace
          </p>
        </div>
      </div>

      {loading && graphs.length === 0 ? (
        <div className="flex items-center justify-center rounded-lg border border-dashed py-12 text-muted-foreground text-sm">
          <Waypoints size={18} className="mr-2 animate-pulse" /> Loading graphs...
        </div>
      ) : graphs.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <Waypoints size={48} className="mb-4 text-muted-foreground/30" />
          <h3 className="mb-2 font-medium">No graphs found</h3>
          <p className="text-sm text-muted-foreground">
            Create named graphs in the Knowledge Graph section to see them here.
          </p>
        </div>
      ) : (
        <div>
          <div className="mb-4 relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              type="text"
              placeholder="Search graphs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border bg-background pl-10 pr-10 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X size={16} />
              </button>
            )}
          </div>

          <div className="rounded-lg border overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50 text-left text-sm">
                  <th className="p-3 font-medium">Graph</th>
                  <th className="p-3 font-medium">Role</th>
                  <th className="p-3 font-medium w-24">Enabled</th>
                </tr>
              </thead>
              <tbody>
                {filteredGraphs.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="p-8 text-center text-muted-foreground">
                      {searchQuery
                        ? `No graphs match "${searchQuery}"`
                        : 'No graphs available'}
                    </td>
                  </tr>
                ) : (
                  filteredGraphs.map((graph) => (
                    <tr
                      key={graph.uri}
                      className="border-b transition-colors hover:bg-muted/30"
                    >
                      <td className="p-3 align-top">
                        <div className="flex items-center gap-3 min-h-[3.25rem]">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                            <Network size={18} className="text-workspace-accent" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="font-medium">{graph.label}</p>
                            <p
                              className="text-xs text-muted-foreground line-clamp-2 min-h-[2rem]"
                              title={graph.uri}
                            >
                              {graph.uri}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="p-3">
                        <span className="text-sm text-muted-foreground truncate">
                          {graph.role_label}
                        </span>
                      </td>
                      <td className="p-3">
                        <button
                          onClick={() => toggleGraph(graph.uri)}
                          className={cn(
                            'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                            graph.enabled ? 'bg-primary' : 'bg-muted'
                          )}
                          title={graph.enabled ? 'Disable graph' : 'Enable graph'}
                        >
                          <span
                            className={cn(
                              'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform',
                              graph.enabled ? 'translate-x-5' : 'translate-x-0.5'
                            )}
                          />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
