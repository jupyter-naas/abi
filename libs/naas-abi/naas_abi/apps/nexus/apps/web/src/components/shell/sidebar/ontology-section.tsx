'use client';

import { useEffect, useMemo, useState, type MouseEvent } from 'react';
import { createPortal } from 'react-dom';
import {
  BrainCircuit, ChevronRight, Box, Network,
  BookOpen, FileCode, Folder,
} from 'lucide-react';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { OntologyDictionary } from './ontology-dictionary';
import { cn } from '@/lib/utils';
import { useOntologyStore } from '@/stores/ontology';
import { useWorkspaceStore } from '@/stores/workspace';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { ontologyBrowser, systemRoute } from '@/lib/ontology-navigation';
import { ontologyApiQuery } from '@/lib/ontology-query';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

type OntologyFile = {
  name: string;
  path: string;
  moduleName: string;
  submoduleName?: string;
  description?: string;
};

type OntologyFileApiItem = {
  name?: string;
  path?: string;
  module_name?: string;
  moduleName?: string;
  submodule_name?: string | null;
  submoduleName?: string | null;
  description?: string | null;
};

type ModuleSubmoduleGroup = {
  moduleName: string;
  filesWithoutSubmodule: OntologyFile[];
  submodules: Array<[string, OntologyFile[]]>;
};

export function OntologySection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const routeQuery = searchParams?.toString() || '';
  const pathname = usePathname();
  const dictionaryMode = ontologyBrowser(routeQuery) === 'dictionary';
  const isSystemHome = searchParams?.get('view') === 'system'
    && !searchParams?.get('subsystem') && !searchParams?.get('process');
  const [ontologyFiles, setOntologyFiles] = useState<OntologyFile[]>([]);
  const [expandedOntologyModules, setExpandedOntologyModules] = useState<string[]>([]);
  const [expandedOntologySubmodules, setExpandedOntologySubmodules] = useState<string[]>([]);
  const [loadingOntologyFiles, setLoadingOntologyFiles] = useState(false);
  const [filesWorkspaceId, setFilesWorkspaceId] = useState<string | null>(null);
  const [filesError, setFilesError] = useState<string | null>(null);
  const { currentWorkspaceId } = useWorkspaceStore();
  const {
    graphRefreshTrigger,
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
    let cancelled = false;
    const fetchOntologyFiles = async () => {
      setLoadingOntologyFiles(true);
      setFilesError(null);
      try {
        const apiUrl = getApiUrl();
        const response = await authFetch(`${apiUrl}/api/ontology/ontologies${ontologyApiQuery()}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch ontology files: ${response.status}`);
        }
        const data = await response.json() as { items?: OntologyFileApiItem[] };
        const files = Array.isArray(data.items) ? data.items : [];
        const normalizedFiles: OntologyFile[] = files.reduce((acc: OntologyFile[], file: OntologyFileApiItem) => {
          if (typeof file?.name !== 'string' || typeof file?.path !== 'string') {
            return acc;
          }
          acc.push({
            name: file.name,
            path: file.path,
            moduleName: file.module_name || file.moduleName || 'Unknown module',
            submoduleName: file.submodule_name || file.submoduleName || undefined,
            description: file.description || undefined,
          });
          return acc;
        }, []).sort((a: OntologyFile, b: OntologyFile) =>
            a.moduleName.localeCompare(b.moduleName, undefined, { sensitivity: 'base' })
            || a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
          );
        if (cancelled) return;
        setOntologyFiles(normalizedFiles);
        setFilesWorkspaceId(currentWorkspaceId);

        setExpandedOntologyModules(
          Array.from(new Set(normalizedFiles.map((file) => file.moduleName)))
        );
        setExpandedOntologySubmodules(
          Array.from(
            new Set(
              normalizedFiles
                .filter((file) => file.submoduleName)
                .map((file) => `${file.moduleName}::${file.submoduleName}`)
            )
          )
        );
      } catch (error) {
        if (cancelled) return;
        setFilesWorkspaceId(currentWorkspaceId);
        setFilesError('Could not load workspace files. Use View → Refresh to retry.');
        console.error('Failed to fetch ontology files:', error);
        setOntologyFiles([]);
        setExpandedOntologyModules([]);
        setExpandedOntologySubmodules([]);
      } finally {
        if (!cancelled) setLoadingOntologyFiles(false);
      }
    };

    fetchOntologyFiles();
    return () => { cancelled = true; };
  }, [currentWorkspaceId, graphRefreshTrigger]);

  useEffect(() => {
    if (pathname !== getWorkspacePath(currentWorkspaceId, '/ontology')) return;
    if (filesWorkspaceId !== currentWorkspaceId || loadingOntologyFiles || filesError) return;
    const route = new URLSearchParams(routeQuery);
    const selected = route.get('ontology');
    const valid = ontologyFiles.some(file => file.path === selected);
    setSelectedOntologyPath(valid ? selected : null);
    if (!dictionaryMode && !selected && ontologyFiles.length) {
      route.set('browser', 'files');
      route.set('ontology', ontologyFiles[0].path);
      router.replace(`?${route}`, { scroll: false });
    }
  }, [currentWorkspaceId, dictionaryMode, filesError, filesWorkspaceId, loadingOntologyFiles, ontologyFiles, pathname, routeQuery, router, setSelectedOntologyPath]);

  function openFile(path: string) {
    const params = new URLSearchParams(routeQuery);
    params.set('browser', 'files');
    params.set('view', 'network');
    params.set('ontology', path);
    params.delete('term'); params.delete('termType');
    router.push(getWorkspacePath(currentWorkspaceId, `/ontology?${params}`));
  }

  return (
    <CollapsibleSection
      id="ontology"
      icon={<BrainCircuit size={18} />}
      label="Ontology"
      description="Define classes, relationships, and schemas"
      href={getWorkspacePath(currentWorkspaceId, '/ontology')}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      {dictionaryMode ? <h2 className="px-2 pb-2 pt-2">
        <button type="button" title="Back to system overview" aria-label="System home"
          onClick={() => router.push(getWorkspacePath(currentWorkspaceId, `/ontology?${systemRoute(routeQuery)}`), { scroll: false })}
          aria-current={isSystemHome ? 'page' : undefined}
          className={cn('flex min-h-8 w-full items-center gap-2 rounded-md px-2 py-1 text-left text-[13px] font-medium hover:bg-workspace-accent-10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-workspace-accent', isSystemHome && 'bg-workspace-accent-10 text-workspace-accent')}>
          <Network size={14} aria-hidden="true" /><span>System</span>
        </button>
      </h2> : <h2 className="px-2 pb-2 pt-2 text-[13px] font-medium">Files</h2>}
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

      {dictionaryMode ? <OntologyDictionary files={filesWorkspaceId === currentWorkspaceId ? ontologyFiles : []} filesLoading={loadingOntologyFiles || filesWorkspaceId !== currentWorkspaceId} filesError={filesWorkspaceId === currentWorkspaceId ? filesError : null} /> : <>
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
                <Folder size={12} className="shrink-0" /><span className="flex-1 truncate">{moduleName}</span>
                <span className="text-xs text-muted-foreground">
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
                          onClick={() => openFile(ontologyFile.path)}
                          className={cn(
                            "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-[13px] leading-5 transition-colors hover:bg-workspace-accent-10",
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
                          <span className="min-w-0 flex-1"><span className="block truncate font-mono text-[13px] leading-5">{ontologyFile.path.split(/[\\/]/).pop()}</span><span className="block truncate text-xs text-muted-foreground">{ontologyFile.name}</span></span>
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
                          <Folder size={12} className="shrink-0" /><span className="flex-1 truncate">{submoduleName}</span>
                          <span className="text-xs text-muted-foreground">{submoduleFiles.length}</span>
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
                                    onClick={() => openFile(ontologyFile.path)}
                                    className={cn(
                                      "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-[13px] leading-5 transition-colors hover:bg-workspace-accent-10",
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
                                    <span className="min-w-0 flex-1"><span className="block truncate font-mono text-[13px] leading-5">{ontologyFile.path.split(/[\\/]/).pop()}</span><span className="block truncate text-xs text-muted-foreground">{ontologyFile.name}</span></span>
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
        {!loadingOntologyFiles && !filesError && filesWorkspaceId === currentWorkspaceId && ontologyFiles.length === 0 && (
          <p className="px-2 py-1 text-xs text-muted-foreground">No ontology files found</p>
        )}
        {filesError && <p role="alert" className="px-2 py-1 text-xs text-destructive">{filesError}</p>}
        {loadingOntologyFiles && (
          <p className="px-2 py-1 text-xs text-muted-foreground">Loading ontologies...</p>
        )}
      </div>

      {/* Reference Ontologies */}
      {referenceOntologies.length > 0 && (
        <div className="space-y-0.5 border-t border-border/50 pt-2 mt-2">
          <p className="px-2 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            References ({referenceOntologies.length})
          </p>
          {referenceOntologies.map((ref) => {
            const isExpanded = expandedReferences.includes(ref.id);
            return (
              <div key={ref.id} className="space-y-0.5">
                <button
                  onClick={() => toggleReference(ref.id)}
                  className="group flex w-full items-center gap-1 rounded-md px-2 py-1 text-left text-[13px] leading-5 transition-colors hover:bg-workspace-accent-10"
                >
                  <ChevronRight
                    size={10}
                    className={cn('flex-shrink-0 transition-transform', isExpanded && 'rotate-90')}
                  />
                  <BookOpen size={12} className="flex-shrink-0 text-amber-500" />
                  <span className="flex-1 truncate font-medium">{ref.name}</span>
                  <span className="text-xs text-muted-foreground">
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
                      <p className="px-2 py-0.5 text-xs text-muted-foreground">
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

      </>}
    </CollapsibleSection>
  );
}
