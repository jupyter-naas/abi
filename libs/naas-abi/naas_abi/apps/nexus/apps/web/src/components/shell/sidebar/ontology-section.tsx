'use client';

import { useEffect, useState } from 'react';
import {
  BrainCircuit, ChevronRight, Box, Link2,
  FolderPlus, RefreshCw, Import, Plus, BookOpen, FileCode,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useOntologyStore } from '@/stores/ontology';
import { useWorkspaceStore } from '@/stores/workspace';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

export function OntologySection({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const [ontologiesExpanded, setOntologiesExpanded] = useState(true);
  const [ontologyFiles, setOntologyFiles] = useState<Array<{ name: string; path: string }>>([]);
  const [loadingOntologyFiles, setLoadingOntologyFiles] = useState(false);
  const { currentWorkspaceId } = useWorkspaceStore();
  const {
    items: ontologyItems,
    loading: ontologyLoading,
    createFolder: createOntologyFolder,
    refreshItems: refreshOntology,
    referenceOntologies,
    expandedReferences,
    toggleReference,
  } = useOntologyStore();

  useEffect(() => {
    const fetchOntologyFiles = async () => {
      setLoadingOntologyFiles(true);
      try {
        const apiUrl = getApiUrl();
        const response = await authFetch(`${apiUrl}/api/ontology/ontologies`);
        if (!response.ok) {
          throw new Error(`Failed to fetch ontology files: ${response.status}`);
        }
        const data = await response.json();
        const files = Array.isArray(data.items) ? data.items : [];
        setOntologyFiles(files);
      } catch (error) {
        console.error('Failed to fetch ontology files:', error);
        setOntologyFiles([]);
      } finally {
        setLoadingOntologyFiles(false);
      }
    };

    fetchOntologyFiles();
  }, []);

  return (
    <CollapsibleSection
      id="ontology"
      icon={<BrainCircuit size={18} />}
      label="Ontology"
      description="Define classes, relationships, and schemas"
      href={getWorkspacePath(currentWorkspaceId, '/ontology')}
      collapsed={collapsed}
    >
      {/* Toolbar */}
      <div className="flex items-center gap-0.5 px-1 pb-1">
        <button
          onClick={() => router.push(getWorkspacePath(currentWorkspaceId, '/ontology?view=create-entity'))}
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="New Class"
        >
          <Box size={14} />
        </button>
        <button
          onClick={() => router.push(getWorkspacePath(currentWorkspaceId, '/ontology?view=create-relationship'))}
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="New Relationship"
        >
          <Link2 size={14} />
        </button>
        <button
          onClick={() => refreshOntology()}
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
            ontologyLoading && "animate-spin"
          )}
          title="Refresh"
        >
          <RefreshCw size={14} />
        </button>
        <button
          onClick={async () => {
            const timestamp = Date.now();
            const name = `Folder_${timestamp}`;
            await createOntologyFolder(name);
          }}
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="New Folder"
        >
          <FolderPlus size={14} />
        </button>
        <button
          onClick={() => {
            router.push(getWorkspacePath(currentWorkspaceId, '/ontology?view=import'));
          }}
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Import Reference Ontology"
        >
          <Import size={14} />
        </button>
      </div>

      {/* Ontologies */}
      <div className="space-y-0.5">
        <button
          onClick={() => setOntologiesExpanded((prev) => !prev)}
          className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground transition-colors hover:bg-workspace-accent-10"
        >
          <ChevronRight
            size={10}
            className={cn('flex-shrink-0 transition-transform', ontologiesExpanded && 'rotate-90')}
          />
          <span>Ontologies ({ontologyFiles.length})</span>
        </button>
        {ontologiesExpanded && (
          <div className="space-y-0.5">
            {ontologyFiles.map((ontologyFile) => (
              <button
                key={ontologyFile.path}
                onClick={() => {
                  const params = new URLSearchParams({
                    view: 'overview',
                    ontology: ontologyFile.path,
                  });
                  router.push(getWorkspacePath(currentWorkspaceId, `/ontology?${params.toString()}`));
                }}
                className="group flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs transition-colors hover:bg-workspace-accent-10"
                title={ontologyFile.path}
              >
                <FileCode size={12} className="flex-shrink-0 text-workspace-accent" />
                <span className="flex-1 truncate">{ontologyFile.name}</span>
                <Plus size={10} className="flex-shrink-0 opacity-0 group-hover:opacity-100 text-muted-foreground" />
              </button>
            ))}
            {!loadingOntologyFiles && ontologyFiles.length === 0 && (
              <p className="px-2 py-1 text-xs text-muted-foreground">No ontology files found</p>
            )}
            {loadingOntologyFiles && (
              <p className="px-2 py-1 text-xs text-muted-foreground">Loading ontologies...</p>
            )}
          </div>
        )}
      </div>

      {/* Reference Ontologies */}
      {referenceOntologies.length > 0 && (
        <div className="space-y-0.5 border-t border-border/50 pt-2 mt-2">
          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            References ({referenceOntologies.length})
          </p>
          {referenceOntologies.map((ref) => {
            const isExpanded = expandedReferences.includes(ref.id);
            return (
              <div key={ref.id} className="space-y-0.5">
                <button
                  onClick={() => toggleReference(ref.id)}
                  className="group flex w-full items-center gap-1 rounded-md px-2 py-1 text-left text-xs transition-colors hover:bg-workspace-accent-10"
                >
                  <ChevronRight
                    size={10}
                    className={cn('flex-shrink-0 transition-transform', isExpanded && 'rotate-90')}
                  />
                  <BookOpen size={12} className="flex-shrink-0 text-amber-500" />
                  <span className="flex-1 truncate font-medium">{ref.name}</span>
                  <span className="text-[10px] text-muted-foreground">
                    {ref.classes.length}c / {ref.properties.length}p
                  </span>
                </button>
                {isExpanded && (
                  <div className="ml-4 space-y-0.5 text-xs">
                    {ref.classes.slice(0, 10).map((cls) => (
                      <button
                        key={cls.iri}
                        onClick={() => {
                          const params = new URLSearchParams({
                            view: 'create-entity',
                            baseClass: cls.iri,
                          });
                          router.push(getWorkspacePath(currentWorkspaceId, `/ontology?${params.toString()}`));
                        }}
                        className="group flex w-full items-center gap-2 rounded-md px-2 py-0.5 text-left transition-colors hover:bg-workspace-accent-10"
                        title={cls.definition || cls.iri}
                      >
                        <Box size={10} className="flex-shrink-0 text-blue-400" />
                        <span className="flex-1 truncate">{cls.label}</span>
                        <Plus size={10} className="flex-shrink-0 opacity-0 group-hover:opacity-100 text-muted-foreground" />
                      </button>
                    ))}
                    {ref.classes.length > 10 && (
                      <p className="px-2 py-0.5 text-[10px] text-muted-foreground">
                        +{ref.classes.length - 10} more classes
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {ontologyItems.length === 0 && referenceOntologies.length === 0 && ontologyFiles.length === 0 && (
        <p className="px-2 py-2 text-xs text-muted-foreground">
          {ontologyLoading ? 'Loading...' : 'No items yet'}
        </p>
      )}
    </CollapsibleSection>
  );
}
