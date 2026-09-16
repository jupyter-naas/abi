'use client';

import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'next/navigation';
import { BrainCircuit, FileCode, Search, X, Tag } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useOntologyCatalogStore,
  type OntologyCatalogItem,
} from '@/stores/ontology-catalog';

/** Trailing filename — the whole path is far too long for a table cell. */
function fileName(path: string): string {
  const segments = path.split('/');
  return segments[segments.length - 1] || path;
}

function OntologyName({ ontology }: { ontology: OntologyCatalogItem }) {
  return (
    <div className="flex items-center gap-3 min-h-[3.25rem]">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
        <FileCode size={18} className="text-muted-foreground" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{ontology.name}</p>
        <p
          className="text-xs text-muted-foreground line-clamp-2 min-h-[2rem]"
          title={ontology.description || ontology.path}
        >
          {ontology.description || ' '}
        </p>
      </div>
    </div>
  );
}

export default function OntologiesSettingsPage() {
  const params = useParams();
  const workspaceId = params?.workspaceId as string | undefined;
  const [mounted, setMounted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const { ontologies, loading, fetchOntologies, toggleOntology } =
    useOntologyCatalogStore();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!workspaceId) return;
    void fetchOntologies(workspaceId);
  }, [workspaceId, fetchOntologies]);

  const filteredOntologies = useMemo(() => {
    const list = ontologies
      .slice()
      .sort(
        (a, b) =>
          a.module_name.localeCompare(b.module_name) || a.name.localeCompare(b.name)
      );
    if (!searchQuery.trim()) return list;
    const q = searchQuery.toLowerCase();
    return list.filter(
      (o) =>
        o.name.toLowerCase().includes(q) ||
        o.module_name.toLowerCase().includes(q) ||
        o.path.toLowerCase().includes(q) ||
        (o.description ?? '').toLowerCase().includes(q)
    );
  }, [ontologies, searchQuery]);

  const enabledCount = useMemo(
    () => ontologies.filter((o) => o.enabled).length,
    [ontologies]
  );

  if (!mounted) {
    return (
      <div className="flex items-center justify-center p-8">
        <p className="text-muted-foreground">Loading ontologies...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Ontologies</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {enabledCount}/{ontologies.length}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Enable or disable the reference ontologies available in this workspace
          </p>
        </div>
      </div>

      {loading && ontologies.length === 0 ? (
        <div className="flex items-center justify-center rounded-lg border border-dashed py-12 text-muted-foreground text-sm">
          <BrainCircuit size={18} className="mr-2 animate-pulse" /> Loading ontologies...
        </div>
      ) : ontologies.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <BrainCircuit size={48} className="mb-4 text-muted-foreground/30" />
          <h3 className="mb-2 font-medium">No ontologies available</h3>
          <p className="text-sm text-muted-foreground">
            Install modules from the Marketplace to see their ontologies here.
          </p>
        </div>
      ) : (
        <div>
          {/* Search */}
          <div className="mb-4 relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              type="text"
              placeholder="Search ontologies..."
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
                  <th className="p-3 font-medium">Ontology</th>
                  <th className="p-3 font-medium">Module</th>
                  <th className="p-3 font-medium">File</th>
                  <th className="p-3 font-medium w-24">Enabled</th>
                </tr>
              </thead>
              <tbody>
                {filteredOntologies.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-muted-foreground">
                      {searchQuery
                        ? `No ontologies match "${searchQuery}"`
                        : 'No ontologies available'}
                    </td>
                  </tr>
                ) : (
                  filteredOntologies.map((ontology) => (
                    <tr
                      key={ontology.ontology_id}
                      className="border-b transition-colors hover:bg-muted/30"
                    >
                      <td className="p-3 align-top">
                        <OntologyName ontology={ontology} />
                      </td>
                      <td className="p-3">
                        <span className="inline-flex items-center gap-1 rounded bg-workspace-accent/10 px-2 py-0.5 text-xs font-medium text-workspace-accent">
                          <Tag size={9} />
                          {ontology.module_name}
                        </span>
                      </td>
                      <td className="p-3">
                        <span
                          className="text-sm text-muted-foreground truncate"
                          title={ontology.path}
                        >
                          {fileName(ontology.path)}
                        </span>
                      </td>
                      <td className="p-3">
                        <button
                          onClick={() => toggleOntology(ontology.ontology_id)}
                          className={cn(
                            'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                            ontology.enabled ? 'bg-primary' : 'bg-muted'
                          )}
                          title={
                            ontology.enabled ? 'Disable ontology' : 'Enable ontology'
                          }
                        >
                          <span
                            className={cn(
                              'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform',
                              ontology.enabled ? 'translate-x-5' : 'translate-x-0.5'
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
