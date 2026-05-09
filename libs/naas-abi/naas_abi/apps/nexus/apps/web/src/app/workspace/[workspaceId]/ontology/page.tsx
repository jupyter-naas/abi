'use client';

import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  Network,
  Eye,
  Download,
  Upload,
  FolderOpen,
  X,
  Box,
  Link2,
  Loader2,
  Search,
  ExternalLink,
  Plus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useOntologyStore,
  type ReferenceClass,
} from '@/stores/ontology';
import {
  useOntologyOverviewGraph,
  useOntologySubclassOptions,
  useOntologySubpropertyOptions,
  useExportOntology,
} from './_hooks/use-ontology-queries';
import { OntologyOverviewView } from './_components/OntologyOverviewView';
import { OntologyNetworkView } from './_components/OntologyNetworkView';
import { OntologySplitView } from './_components/OntologySplitView';
import type {
  OntologyOverviewGraphEdge,
  OntologyOverviewGraphNode,
  ViewMode,
} from './_components/types';

export default function OntologyPage() {
  const searchParams = useSearchParams();
  const requestedInitialView = (searchParams?.get('view') as ViewMode) || 'network';
  const initialView: ViewMode = requestedInitialView === 'editor' ? 'classes' : requestedInitialView;
  
  const [viewMode, setViewMode] = useState<ViewMode>(initialView);
  const [lastCatalogView, setLastCatalogView] = useState<'classes' | 'relations'>(
    initialView === 'relations' ? 'relations' : 'classes'
  );
  const [importPath, setImportPath] = useState('');
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  
  // Creation form state
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formExample, setFormExample] = useState('');
  const [formBaseRef, setFormBaseRef] = useState<string>(''); // IRI of selected base class/property (reference)
  const [formSubclassOf, setFormSubclassOf] = useState<string>(''); // IRI of parent class from selected ontology
  const [formSubpropertyOf, setFormSubpropertyOf] = useState<string>('');
  const [formDomain, setFormDomain] = useState<string>('');
  const [formRange, setFormRange] = useState<string>('');
  const [formSearchQuery, setFormSearchQuery] = useState('');
  const [creating, setCreating] = useState(false);
  
  // Update view mode and pre-fill form when URL changes
  useEffect(() => {
    const view = searchParams?.get('view') as ViewMode;
    if (view && ['overview', 'network', 'classes', 'relations', 'editor', 'import', 'export', 'create-entity', 'create-relationship'].includes(view)) {
      const normalizedView = view === 'editor' ? 'classes' : view;
      setViewMode(normalizedView);
      if (normalizedView === 'classes' || normalizedView === 'relations') {
        setLastCatalogView(normalizedView);
      } else if (normalizedView === 'create-entity') {
        setLastCatalogView('classes');
      } else if (normalizedView === 'create-relationship') {
        setLastCatalogView('relations');
      }
      
      // Pre-fill base class/property from URL if provided
      const baseClass = searchParams?.get('baseClass');
      const baseProperty = searchParams?.get('baseProperty');
      if (baseClass) {
        setFormBaseRef(baseClass);
      } else if (baseProperty) {
        setFormBaseRef(baseProperty);
      }
    }
  }, [searchParams]);

  const {
    items,
    selectedItemId,
    referenceOntologies,
    importReferenceOntology,
    createEntity,
    createRelationship,
    setSelectedItem,
    updateItem,
    fetchItemsForView,
  } = useOntologyStore();

  const selectedItem = items.find((i) => i.id === selectedItemId);
  const classItems = useMemo(() => items.filter((item) => item.type === 'entity'), [items]);
  const relationshipItems = useMemo(() => items.filter((item) => item.type === 'relationship'), [items]);
  const selectedOntologyPath = searchParams?.get('ontology') || null;

  // Overview graph drives both the Overview (lists) and Network tabs. The query
  // stays mounted across tab switches so navigating Overview ↔ Network is free.
  const overviewGraphQuery = useOntologyOverviewGraph({
    ontologyPath: selectedOntologyPath,
    enabled: viewMode === 'overview' || viewMode === 'network',
  });
  const overviewGraphNodes: OntologyOverviewGraphNode[] = useMemo(
    () =>
      (overviewGraphQuery.data?.nodes ?? []).map((n) => ({
        id: n.id,
        label: n.label,
        type: n.type,
        properties: n.properties ?? {},
      })),
    [overviewGraphQuery.data],
  );
  const overviewGraphEdges: OntologyOverviewGraphEdge[] = useMemo(
    () =>
      (overviewGraphQuery.data?.edges ?? []).map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
        label: e.label,
        properties: e.properties,
      })),
    [overviewGraphQuery.data],
  );
  const loadingOverviewGraph = overviewGraphQuery.isPending;
  const overviewGraphError = overviewGraphQuery.error
    ? 'Failed to load ontology graph.'
    : null;

  // When on Export view but no ontology is selected, return to overview (Export not available)
  useEffect(() => {
    if (viewMode === 'export' && !selectedOntologyPath) {
      setViewMode('network');
    }
  }, [viewMode, selectedOntologyPath]);

  useEffect(() => {
    if (viewMode === 'classes') {
      fetchItemsForView('classes', selectedOntologyPath);
    } else if (viewMode === 'relations') {
      fetchItemsForView('relations', selectedOntologyPath);
    }
  }, [viewMode, fetchItemsForView, selectedOntologyPath]);

  // Aggregate all classes and properties from all references
  const allClasses = useMemo(() => {
    const classes: Array<ReferenceClass & { ontologyName: string }> = [];
    referenceOntologies.forEach((ref) => {
      ref.classes.forEach((cls) => {
        classes.push({ ...cls, ontologyName: ref.name });
      });
    });
    return classes;
  }, [referenceOntologies]);

  const handleImport = async () => {
    if (!importPath.trim()) return;

    setImporting(true);
    setImportError(null);

    try {
      const result = await importReferenceOntology(importPath.trim());
      if (result) {
        setImportPath('');
        setViewMode('network');
      } else {
        setImportError('Failed to import ontology. Check the file path.');
      }
    } catch (err) {
      setImportError('Error importing ontology');
    } finally {
      setImporting(false);
    }
  };

  const resetForm = () => {
    setFormName('');
    setFormDescription('');
    setFormExample('');
    setFormBaseRef('');
    setFormSubclassOf('');
    setFormSubpropertyOf('');
    setFormDomain('');
    setFormRange('');
    setFormSearchQuery('');
  };

  // Subclass / Subproperty options for the New Class / New Object Property forms.
  const subclassOptionsQuery = useOntologySubclassOptions({
    ontologyPath: selectedOntologyPath,
    enabled: viewMode === 'create-entity' || viewMode === 'create-relationship',
  });
  const subclassOptions = subclassOptionsQuery.data ?? [];
  const loadingSubclassOptions = subclassOptionsQuery.isFetching;

  const subpropertyOptionsQuery = useOntologySubpropertyOptions({
    ontologyPath: selectedOntologyPath,
    enabled: viewMode === 'create-relationship',
  });
  const subpropertyOptions = subpropertyOptionsQuery.data ?? [];
  const loadingSubpropertyOptions = subpropertyOptionsQuery.isFetching;

  const openCreateEntity = () => {
    resetForm();
    setLastCatalogView('classes');
    setViewMode('create-entity');
  };

  const openCreateRelationship = () => {
    resetForm();
    setLastCatalogView('relations');
    setViewMode('create-relationship');
  };

  const handleSubmitEntity = async () => {
    if (!formName.trim()) return;
    setCreating(true);
    try {
      await createEntity(
        formName.trim(),
        formDescription.trim() || undefined,
        formSubclassOf || undefined,
        formExample.trim() || undefined
      );
      resetForm();
      setViewMode('classes');
      setLastCatalogView('classes');
    } finally {
      setCreating(false);
    }
  };

  const handleSubmitRelationship = async () => {
    if (!formName.trim()) return;
    setCreating(true);
    try {
      await createRelationship(
        formName.trim(),
        formDescription.trim() || undefined,
        formExample.trim() || undefined,
        formSubpropertyOf || undefined,
        formDomain ? [formDomain] : undefined,
        formRange ? [formRange] : undefined
      );
      resetForm();
      setViewMode('relations');
      setLastCatalogView('relations');
    } finally {
      setCreating(false);
    }
  };

  const exportMutation = useExportOntology();
  const handleExportCurrentOntology = async () => {
    if (!selectedOntologyPath || exportMutation.isPending) return;
    try {
      await exportMutation.mutateAsync(selectedOntologyPath);
    } catch (error) {
      console.error('Failed to export ontology:', error);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <Header />

      <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex h-10 shrink-0 items-center justify-between border-b bg-muted/30 px-4">
          <div className="flex gap-1">
            <button
              onClick={() => setViewMode('network')}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
                viewMode === 'network' ? 'bg-background' : 'text-muted-foreground hover:bg-background'
              )}
            >
              <Network size={14} />
              Network
            </button>
            <button
              onClick={() => setViewMode('overview')}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
                viewMode === 'overview' ? 'bg-background' : 'text-muted-foreground hover:bg-background'
              )}
            >
              <Eye size={14} />
              Metrics
            </button>
            <button
              onClick={() => {
                setLastCatalogView('classes');
                setViewMode('classes');
              }}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
                viewMode === 'classes' ? 'bg-background' : 'text-muted-foreground hover:bg-background'
              )}
            >
              <Box size={14} />
              Classes
            </button>
            <button
              onClick={() => {
                setLastCatalogView('relations');
                setViewMode('relations');
              }}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
                viewMode === 'relations' ? 'bg-background' : 'text-muted-foreground hover:bg-background'
              )}
            >
              <Link2 size={14} />
              Object Properties
            </button>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setViewMode('import')}
              className={cn(
                'flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground',
                viewMode === 'import' && 'text-foreground'
              )}
            >
              <Upload size={14} />
              Import
            </button>
            <button
              onClick={() => setViewMode('export')}
              disabled={!selectedOntologyPath}
              className={cn(
                'flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground',
                viewMode === 'export' && 'text-foreground',
                !selectedOntologyPath && 'cursor-not-allowed'
              )}
              title={!selectedOntologyPath ? 'Select an ontology in Metrics to export' : 'Export selected ontology'}
            >
              <Download size={14} />
              Export
            </button>
          </div>
        </div>

        {/* Content - scrollable */}
        <div className="flex flex-1 min-h-0 overflow-y-auto">
          {viewMode === 'import' && (
            <div className="flex min-h-full w-full flex-col items-center justify-center bg-card p-8">
              <div className="w-full max-w-xl">
                <div className="mb-6 text-center">
                  <div className="mb-4 flex justify-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                      <Upload size={32} className="text-muted-foreground" />
                    </div>
                  </div>
                  <h2 className="mb-2 text-lg font-semibold">Import Reference Ontology</h2>
                  <p className="text-muted-foreground">
                    Import TTL, OWL, or RDF files to use as reference when creating entities.
                  </p>
                </div>

                <div className="space-y-4">
                  {/* File path input */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">
                      File Path
                    </label>
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <FolderOpen size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                        <input
                          type="text"
                          value={importPath}
                          onChange={(e) => setImportPath(e.target.value)}
                          placeholder="/path/to/ontology.ttl"
                          className="w-full rounded-lg border bg-background py-2 pl-10 pr-4 text-sm outline-none focus:ring-2 focus:ring-primary"
                        />
                      </div>
                      <button
                        onClick={handleImport}
                        disabled={!importPath.trim() || importing}
                        className={cn(
                          'flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                          'hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed'
                        )}
                      >
                        {importing ? (
                          <Loader2 size={16} className="animate-spin" />
                        ) : (
                          <Upload size={16} />
                        )}
                        Import
                      </button>
                    </div>
                    {importError && (
                      <p className="mt-2 text-sm text-red-500">{importError}</p>
                    )}
                  </div>

                  {/* Supported formats */}
                  <div className="text-center text-xs text-muted-foreground">
                    Supported: .ttl (Turtle), .owl (OWL), .rdf (RDF/XML)
                  </div>
                </div>
              </div>
            </div>
          )}

          {viewMode === 'export' && selectedOntologyPath && (
            <div className="flex min-h-full w-full flex-col items-center justify-center bg-card p-8">
              <div className="w-full max-w-xl">
                <div className="mb-6 text-center">
                  <div className="mb-4 flex justify-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                      <Download size={32} className="text-muted-foreground" />
                    </div>
                  </div>
                  <h2 className="mb-2 text-lg font-semibold">Export Ontology</h2>
                  <p className="text-muted-foreground">
                    Download the selected ontology as a TTL file.
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="rounded-lg border bg-muted/30 p-4">
                    <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Selected ontology
                    </p>
                    <p className="truncate font-mono text-sm" title={selectedOntologyPath}>
                      {selectedOntologyPath}
                    </p>
                  </div>

                  <div className="flex justify-center">
                    <button
                      onClick={handleExportCurrentOntology}
                      disabled={exportMutation.isPending}
                      className={cn(
                        'flex items-center gap-2 rounded-lg bg-workspace-accent px-6 py-2.5 text-sm font-medium text-white',
                        'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50'
                      )}
                    >
                      {exportMutation.isPending ? (
                        <Loader2 size={16} className="animate-spin" />
                      ) : (
                        <Download size={16} />
                      )}
                      {exportMutation.isPending ? 'Exporting...' : 'Export ontology'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {viewMode === 'overview' && (
            <div className="min-h-full w-full">
              <OntologyOverviewView
                ontologyPath={selectedOntologyPath}
                graphNodes={overviewGraphNodes}
                graphEdges={overviewGraphEdges}
                loadingGraph={loadingOverviewGraph}
                graphError={overviewGraphError}
                onSelectClass={(classId) => {
                  setSelectedItem(classId);
                  setLastCatalogView('classes');
                  setViewMode('classes');
                }}
                onSelectRelationship={(relationshipId) => {
                  setSelectedItem(relationshipId);
                  setLastCatalogView('relations');
                  setViewMode('relations');
                }}
                onCreateEntity={openCreateEntity}
                onCreateRelationship={openCreateRelationship}
              />
            </div>
          )}

          {viewMode === 'network' && (
            <OntologyNetworkView
              key={selectedOntologyPath ?? 'all'}
              ontologyPath={selectedOntologyPath}
              graphNodes={overviewGraphNodes}
              graphEdges={overviewGraphEdges}
              loadingGraph={loadingOverviewGraph}
              graphError={overviewGraphError}
            />
          )}

          {(viewMode === 'classes' || viewMode === 'relations' || viewMode === 'editor') && (
            <OntologySplitView
              mode={viewMode === 'relations' ? 'relations' : 'classes'}
              items={viewMode === 'relations' ? relationshipItems : classItems}
              selectedItemId={selectedItemId}
              selectedItem={selectedItem}
              onSelectItem={setSelectedItem}
              allClasses={allClasses}
              onUpdateItem={(itemId, updates) => updateItem(itemId, updates)}
              onCreateEntity={openCreateEntity}
              onCreateRelationship={openCreateRelationship}
            />
          )}

          {/* New Class Form */}
          {viewMode === 'create-entity' && (
            <div className="flex min-h-full w-full flex-col bg-card p-6">
              <div className="mx-auto w-full max-w-2xl">
                <div className="mb-6 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Box size={24} className="text-blue-500" />
                    <h2 className="text-lg font-semibold">New Class</h2>
                  </div>
                  <button
                    onClick={() => setViewMode(lastCatalogView)}
                    className="rounded p-2 text-muted-foreground hover:bg-muted"
                  >
                    <X size={20} />
                  </button>
                </div>

                <div className="space-y-6">
                  {/* Name */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">Name *</label>
                    <input
                      type="text"
                      value={formName}
                      onChange={(e) => setFormName(e.target.value)}
                      placeholder="e.g., Customer, Product, Order"
                      className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  {/* Definition */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">Definition</label>
                    <textarea
                      value={formDescription}
                      onChange={(e) => setFormDescription(e.target.value)}
                      placeholder="Define what this class represents..."
                      rows={3}
                      className="w-full resize-none rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  {/* Example */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">Example</label>
                    <input
                      type="text"
                      value={formExample}
                      onChange={(e) => setFormExample(e.target.value)}
                      placeholder="e.g., Person, Order, Event"
                      className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  {/* Subclass Of (classes from selected ontology or all ontologies) */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">
                      Subclass Of
                      <span className="ml-2 text-xs font-normal text-muted-foreground">(optional)</span>
                    </label>
                    {loadingSubclassOptions ? (
                      <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                        <Loader2 size={14} className="animate-spin" />
                        Loading classes...
                      </div>
                    ) : (
                      <select
                        value={formSubclassOf}
                        onChange={(e) => setFormSubclassOf(e.target.value)}
                        className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      >
                        <option value="">None</option>
                        {subclassOptions.map((cls) => (
                          <option key={cls.id} value={cls.id} title={cls.id}>
                            {cls.name || cls.id}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex gap-3 pt-4">
                    <button
                      onClick={() => setViewMode(lastCatalogView)}
                      className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSubmitEntity}
                      disabled={!formName.trim() || creating}
                      className={cn(
                        'flex flex-1 items-center justify-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                        'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50'
                      )}
                    >
                      {creating ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                      Create Class
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Create Object Property Form */}
          {viewMode === 'create-relationship' && (
            <div className="flex min-h-full w-full flex-col bg-card p-6">
              <div className="mx-auto w-full max-w-2xl">
                <div className="mb-6 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Link2 size={24} className="text-green-500" />
                    <h2 className="text-lg font-semibold">New Object Property</h2>
                  </div>
                  <button
                    onClick={() => setViewMode(lastCatalogView)}
                    className="rounded p-2 text-muted-foreground hover:bg-muted"
                  >
                    <X size={20} />
                  </button>
                </div>

                <div className="space-y-6">
                  {/* Name */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">Name *</label>
                    <input
                      type="text"
                      value={formName}
                      onChange={(e) => setFormName(e.target.value)}
                      placeholder="e.g., hasParticipant, realizesProcess"
                      className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  {/* Definition */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">Definition</label>
                    <textarea
                      value={formDescription}
                      onChange={(e) => setFormDescription(e.target.value)}
                      placeholder="Define what this object property represents..."
                      rows={3}
                      className="w-full resize-none rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  {/* Example */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">Example</label>
                    <input
                      type="text"
                      value={formExample}
                      onChange={(e) => setFormExample(e.target.value)}
                      placeholder="e.g., Person hasParticipant Event"
                      className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  {/* Subproperty Of */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">
                      Subproperty Of
                      <span className="ml-2 text-xs font-normal text-muted-foreground">(optional)</span>
                    </label>
                    {loadingSubpropertyOptions ? (
                      <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                        <Loader2 size={14} className="animate-spin" />
                        Loading properties...
                      </div>
                    ) : (
                      <select
                        value={formSubpropertyOf}
                        onChange={(e) => setFormSubpropertyOf(e.target.value)}
                        className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      >
                        <option value="">None</option>
                        {subpropertyOptions.map((prop) => (
                          <option key={prop.id} value={prop.id} title={prop.id}>
                            {prop.name || prop.id}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  {/* Domain */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">
                      Domain
                      <span className="ml-2 text-xs font-normal text-muted-foreground">(optional)</span>
                    </label>
                    <p className="mb-2 text-xs text-muted-foreground">
                      'Domain' defines where a relationship starts from (e.g., in &quot;Teacher teaches Course&quot;, the relationship starts from Teacher).
                    </p>
                    {loadingSubclassOptions ? (
                      <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                        <Loader2 size={14} className="animate-spin" />
                        Loading classes...
                      </div>
                    ) : (
                      <select
                        value={formDomain}
                        onChange={(e) => setFormDomain(e.target.value)}
                        className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      >
                        <option value="">None</option>
                        {subclassOptions.map((cls) => (
                          <option key={cls.id} value={cls.id} title={cls.id}>
                            {cls.name || cls.id}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  {/* Range */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">
                      Range
                      <span className="ml-2 text-xs font-normal text-muted-foreground">(optional)</span>
                    </label>
                    <p className="mb-2 text-xs text-muted-foreground">
                      'Range' defines where a relationship goes to (e.g., in &quot;Teacher teaches Course&quot;, the relationship goes to Course).
                    </p>
                    {loadingSubclassOptions ? (
                      <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                        <Loader2 size={14} className="animate-spin" />
                        Loading classes...
                      </div>
                    ) : (
                      <select
                        value={formRange}
                        onChange={(e) => setFormRange(e.target.value)}
                        className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      >
                        <option value="">None</option>
                        {subclassOptions.map((cls) => (
                          <option key={cls.id} value={cls.id} title={cls.id}>
                            {cls.name || cls.id}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex gap-3 pt-4">
                    <button
                      onClick={() => setViewMode(lastCatalogView)}
                      className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSubmitRelationship}
                      disabled={!formName.trim() || creating}
                      className={cn(
                        'flex flex-1 items-center justify-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                        'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50'
                      )}
                    >
                      {creating ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                      Create Object Property
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
