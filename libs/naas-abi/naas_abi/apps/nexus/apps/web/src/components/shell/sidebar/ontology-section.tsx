'use client';

import { useEffect, useMemo, useState, type MouseEvent } from 'react';
import { createPortal } from 'react-dom';
import {
  BrainCircuit, ChevronRight, Box, Link2,
  RefreshCw, Import, BookOpen, FileCode,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useOntologyStore } from '@/stores/ontology';
import { useOntologyConfigsStore } from '@/stores/ontology-configs';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

type OntologyFile = {
  name: string;
  path: string;
  moduleName: string;
  submoduleName?: string;
  description?: string;
};

type ModuleSubmoduleGroup = {
  moduleName: string;
  filesWithoutSubmodule: OntologyFile[];
  submodules: Array<[string, OntologyFile[]]>;
};

export function OntologySection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const router = useRouter();
  const [expandedOntologyModules, setExpandedOntologyModules] = useState<string[]>([]);
  const [expandedOntologySubmodules, setExpandedOntologySubmodules] = useState<string[]>([]);
  const { currentWorkspaceId } = useWorkspaceStore();
  const {
    ontologies: ontologyConfigItems,
    loading: loadingOntologyFiles,
    fetchOntologies,
  } = useOntologyConfigsStore();
  const {
    items: ontologyItems,
    loading: ontologyLoading,
    refreshItems: refreshOntology,
    referenceOntologies,
    expandedReferences,
    toggleReference,
    selectedOntologyPath,
    setSelectedOntologyPath,
  } = useOntologyStore();
  const [ontologyTooltip, setOntologyTooltip] = useState<{
    name: string;
    description: string;
    position: { top: number; left: number };
  } | null>(null);

  const showOntologyTooltip = (
    event: MouseEvent<HTMLButtonElement>,
    name: string,
    description: string
  ) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setOntologyTooltip({
      name,
      description,
      position: {
        top: rect.top,
        left: rect.right + 8,
      },
    });
  };

  const ontologyFiles = useMemo<OntologyFile[]>(() => (
    ontologyConfigItems
      .filter((item) => item.enabled)
      .map((item) => ({
        name: item.name,
        path: item.path,
        moduleName: item.module_name || 'Unknown module',
        submoduleName: item.submodule_name || undefined,
        description: item.description || undefined,
      }))
      .sort((a, b) =>
        a.moduleName.localeCompare(b.moduleName, undefined, { sensitivity: 'base' })
        || a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
      )
  ), [ontologyConfigItems]);

  const groupedOntologyFiles = useMemo(() => {
    const grouped = new Map<string, OntologyFile[]>();
    for (const ontologyFile of ontologyFiles) {
      if (!grouped.has(ontologyFile.moduleName)) {
        grouped.set(ontologyFile.moduleName, []);
      }
      grouped.get(ontologyFile.moduleName)?.push(ontologyFile);
    }
    return Array.from(grouped.entries());
  }, [ontologyFiles]);

  const groupedByModuleAndSubmodule = useMemo<ModuleSubmoduleGroup[]>(() => (
    groupedOntologyFiles.map(([moduleName, moduleFiles]: [string, OntologyFile[]]) => {
      const filesWithoutSubmodule = moduleFiles.filter((file) => !file.submoduleName);
      const submodulesMap = new Map<string, OntologyFile[]>();
      for (const file of moduleFiles) {
        if (!file.submoduleName) {
          continue;
        }
        if (!submodulesMap.has(file.submoduleName)) {
          submodulesMap.set(file.submoduleName, []);
        }
        submodulesMap.get(file.submoduleName)?.push(file);
      }
      const submodules = Array.from(submodulesMap.entries()).sort(([a], [b]) => (
        a.localeCompare(b, undefined, { sensitivity: 'base' })
      ));
      return { moduleName, filesWithoutSubmodule, submodules };
    })
  ), [groupedOntologyFiles]);

  useEffect(() => {
    if (currentWorkspaceId) {
      void fetchOntologies(currentWorkspaceId);
    }
  }, [currentWorkspaceId, fetchOntologies]);

  useEffect(() => {
    // Auto-select and navigate to the first ontology when none is selected
    // (or when the currently-selected one is no longer visible).
    const currentSelected = useOntologyStore.getState().selectedOntologyPath;
    const stillVisible = currentSelected
      ? ontologyFiles.some((file) => file.path === currentSelected)
      : false;
    if (!stillVisible && ontologyFiles.length > 0) {
      const firstPath = ontologyFiles[0].path;
      setSelectedOntologyPath(firstPath);
      const params = new URLSearchParams({ view: 'network', ontology: firstPath });
      router.push(getWorkspacePath(currentWorkspaceId, `/ontology?${params.toString()}`));
    }
    setExpandedOntologyModules(
      Array.from(new Set(ontologyFiles.map((file) => file.moduleName)))
    );
    setExpandedOntologySubmodules(
      Array.from(
        new Set(
          ontologyFiles
            .filter((file) => file.submoduleName)
            .map((file) => `${file.moduleName}::${file.submoduleName}`)
        )
      )
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ontologyFiles]);

  return (
    <CollapsibleSection
      id="ontology"
      icon={<BrainCircuit size={18} />}
      label="Ontology"
      description="Define classes, relationships, and schemas"
      href={getWorkspacePath(currentWorkspaceId, '/ontology?view=network')}
      collapsed={collapsed}
      detailOnly={detailOnly}
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
          title="New Object Property"
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
          onClick={() => {
            router.push(getWorkspacePath(currentWorkspaceId, '/ontology?view=import'));
          }}
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Import Reference Ontology"
        >
          <Import size={14} />
        </button>
      </div>
      {ontologyTooltip && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed z-[100] whitespace-nowrap rounded-md border border-border bg-popover px-3 py-2 text-sm shadow-lg animate-in fade-in-0 zoom-in-95 duration-100"
          style={{
            top: ontologyTooltip.position.top,
            left: ontologyTooltip.position.left,
          }}
        >
          <p className="font-medium">{ontologyTooltip.name}</p>
          <p className="text-xs text-muted-foreground">{ontologyTooltip.description}</p>
        </div>,
        document.body
      )}

      {/* Ontologies by module */}
      <div className="space-y-0.5">
        {groupedByModuleAndSubmodule.map((group: ModuleSubmoduleGroup) => {
          const { moduleName, filesWithoutSubmodule, submodules } = group;
          const moduleExpanded = expandedOntologyModules.includes(moduleName);
          return (
            <div key={moduleName} className="space-y-0.5">
              <button
                onClick={() => setExpandedOntologyModules((prev: string[]) => (
                  prev.includes(moduleName)
                    ? prev.filter((value: string) => value !== moduleName)
                    : [...prev, moduleName]
                ))}
                className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-left text-xs font-medium text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-foreground"
              >
                <ChevronRight
                  size={10}
                  className={cn('flex-shrink-0 transition-transform', moduleExpanded && 'rotate-90')}
                />
                <span className="flex-1 truncate">{moduleName}</span>
                <span className="text-[10px] text-muted-foreground">
                  {filesWithoutSubmodule.length + submodules.reduce(
                    (acc: number, entry: [string, OntologyFile[]]) => acc + entry[1].length,
                    0
                  )}
                </span>
              </button>
              {moduleExpanded && (
                <div className="ml-4 space-y-0.5">
                  {filesWithoutSubmodule.map((ontologyFile: OntologyFile) => (
                    (() => {
                      const isSelected = selectedOntologyPath === ontologyFile.path;
                      const ontologyDescription = ontologyFile.description
                        || `${ontologyFile.moduleName} - ${ontologyFile.path}`;
                      return (
                        <button
                          key={`${moduleName}:${ontologyFile.path}`}
                          onClick={() => {
                            setSelectedOntologyPath(ontologyFile.path);
                            const params = new URLSearchParams({
                              view: 'network',
                              ontology: ontologyFile.path,
                            });
                            router.push(getWorkspacePath(currentWorkspaceId, `/ontology?${params.toString()}`));
                          }}
                          className={cn(
                            "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs transition-colors hover:bg-workspace-accent-10",
                            isSelected && "bg-workspace-accent-10 text-workspace-accent"
                          )}
                          onMouseEnter={(event) => showOntologyTooltip(
                            event,
                            ontologyFile.name,
                            ontologyDescription
                          )}
                          onMouseLeave={() => setOntologyTooltip(null)}
                          aria-current={isSelected ? 'page' : undefined}
                        >
                          <FileCode size={12} className="flex-shrink-0 text-workspace-accent" />
                          <span className="flex-1 truncate">{ontologyFile.name}</span>
                        </button>
                      );
                    })()
                  ))}
                  {submodules.map((entry: [string, OntologyFile[]]) => {
                    const [submoduleName, submoduleFiles] = entry;
                    const submoduleKey = `${moduleName}::${submoduleName}`;
                    const submoduleExpanded = expandedOntologySubmodules.includes(submoduleKey);
                    return (
                      <div key={submoduleKey} className="space-y-0.5">
                        <button
                          onClick={() => setExpandedOntologySubmodules((prev: string[]) => (
                            prev.includes(submoduleKey)
                              ? prev.filter((value: string) => value !== submoduleKey)
                              : [...prev, submoduleKey]
                          ))}
                          className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-left text-xs text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-foreground"
                        >
                          <ChevronRight
                            size={10}
                            className={cn('flex-shrink-0 transition-transform', submoduleExpanded && 'rotate-90')}
                          />
                          <span className="flex-1 truncate">{submoduleName}</span>
                          <span className="text-[10px] text-muted-foreground">{submoduleFiles.length}</span>
                        </button>
                        {submoduleExpanded && (
                          <div className="ml-4 space-y-0.5">
                            {submoduleFiles.map((ontologyFile: OntologyFile) => (
                              (() => {
                                const isSelected = selectedOntologyPath === ontologyFile.path;
                                const ontologyDescription = ontologyFile.description
                                  || `${ontologyFile.moduleName} / ${submoduleName} - ${ontologyFile.path}`;
                                return (
                                  <button
                                    key={`${submoduleKey}:${ontologyFile.path}`}
                                    onClick={() => {
                                      setSelectedOntologyPath(ontologyFile.path);
                                      const params = new URLSearchParams({
                                        view: 'network',
                                        ontology: ontologyFile.path,
                                      });
                                      router.push(getWorkspacePath(currentWorkspaceId, `/ontology?${params.toString()}`));
                                    }}
                                    className={cn(
                                      "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs transition-colors hover:bg-workspace-accent-10",
                                      isSelected && "bg-workspace-accent-10 text-workspace-accent"
                                    )}
                                    onMouseEnter={(event) => showOntologyTooltip(
                                      event,
                                      ontologyFile.name,
                                      ontologyDescription
                                    )}
                                    onMouseLeave={() => setOntologyTooltip(null)}
                                    aria-current={isSelected ? 'page' : undefined}
                                  >
                                    <FileCode size={12} className="flex-shrink-0 text-workspace-accent" />
                                    <span className="flex-1 truncate">{ontologyFile.name}</span>
                                  </button>
                                );
                              })()
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
        {!loadingOntologyFiles && ontologyFiles.length === 0 && (
          <p className="px-2 py-1 text-xs text-muted-foreground">No ontology files found</p>
        )}
        {loadingOntologyFiles && (
          <p className="px-2 py-1 text-xs text-muted-foreground">Loading ontologies...</p>
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
                        className="flex w-full items-center gap-2 rounded-md px-2 py-0.5 text-left transition-colors hover:bg-workspace-accent-10"
                        title={cls.definition || cls.iri}
                      >
                        <Box size={10} className="flex-shrink-0 text-blue-400" />
                        <span className="flex-1 truncate">{cls.label}</span>
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
