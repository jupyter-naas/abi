'use client';

import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import {
  Network,
  Plus,
  Eye,
  Download,
  Upload,
  FolderOpen,
  X,
  Box,
  Link2,
  ChevronRight,
  Loader2,
  Check,
  Search,
  Star,
  MoreHorizontal,
  ExternalLink,
  Mail,
  Pencil,
  LayoutGrid,
  Users,
  Type,
  Hash,
  Calendar,
  ToggleLeft,
  List,
  HelpCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOntologyStore, type ReferenceClass, type ReferenceProperty, type OntologyItem, type EntityProperty, type EntityStatus, type EntityVisibility } from '@/stores/ontology';

type ViewMode = 'overview' | 'classes' | 'relations' | 'editor' | 'import' | 'create-entity' | 'create-relationship';

export default function OntologyPage() {
  const searchParams = useSearchParams();
  const requestedInitialView = (searchParams?.get('view') as ViewMode) || 'overview';
  const initialView: ViewMode = requestedInitialView === 'editor' ? 'classes' : requestedInitialView;
  
  const [viewMode, setViewMode] = useState<ViewMode>(initialView);
  const [lastCatalogView, setLastCatalogView] = useState<'classes' | 'relations'>(
    initialView === 'relations' ? 'relations' : 'classes'
  );
  const [importPath, setImportPath] = useState('');
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  
  // Creation form state
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formBaseRef, setFormBaseRef] = useState<string>(''); // IRI of selected base class/property
  const [formSearchQuery, setFormSearchQuery] = useState('');
  const [creating, setCreating] = useState(false);
  
  // Update view mode and pre-fill form when URL changes
  useEffect(() => {
    const view = searchParams?.get('view') as ViewMode;
    if (view && ['overview', 'classes', 'relations', 'editor', 'import', 'create-entity', 'create-relationship'].includes(view)) {
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

  const allProperties = useMemo(() => {
    const properties: Array<ReferenceProperty & { ontologyName: string }> = [];
    referenceOntologies.forEach((ref) => {
      ref.properties.forEach((prop) => {
        properties.push({ ...prop, ontologyName: ref.name });
      });
    });
    return properties;
  }, [referenceOntologies]);

  // Filter classes/properties by search query
  const filteredClasses = useMemo(() => {
    if (!formSearchQuery.trim()) return allClasses;
    const query = formSearchQuery.toLowerCase();
    return allClasses.filter(
      (cls) =>
        cls.label.toLowerCase().includes(query) ||
        cls.definition?.toLowerCase().includes(query) ||
        cls.ontologyName.toLowerCase().includes(query)
    );
  }, [allClasses, formSearchQuery]);

  const filteredProperties = useMemo(() => {
    if (!formSearchQuery.trim()) return allProperties;
    const query = formSearchQuery.toLowerCase();
    return allProperties.filter(
      (prop) =>
        prop.label.toLowerCase().includes(query) ||
        prop.definition?.toLowerCase().includes(query) ||
        prop.ontologyName.toLowerCase().includes(query)
    );
  }, [allProperties, formSearchQuery]);

  const handleImport = async () => {
    if (!importPath.trim()) return;

    setImporting(true);
    setImportError(null);

    try {
      const result = await importReferenceOntology(importPath.trim());
      if (result) {
        setImportPath('');
        setViewMode('overview');
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
    setFormBaseRef('');
    setFormSearchQuery('');
  };

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
      await createEntity(formName.trim(), formDescription.trim() || undefined, formBaseRef || undefined);
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
      await createRelationship(formName.trim(), formDescription.trim() || undefined, formBaseRef || undefined);
      resetForm();
      setViewMode('relations');
      setLastCatalogView('relations');
    } finally {
      setCreating(false);
    }
  };

  const selectedBaseClass = allClasses.find((c) => c.iri === formBaseRef);
  const selectedBaseProperty = allProperties.find((p) => p.iri === formBaseRef);

  const handleExportCurrentOntology = async () => {
    if (!selectedOntologyPath || exporting) return;

    setExporting(true);
    try {
      const baseUrl = getApiUrl();
      const response = await authFetch(
        `${baseUrl}/api/ontology/export?ontology_path=${encodeURIComponent(selectedOntologyPath)}`
      );
      if (!response.ok) {
        throw new Error(`Failed to export ontology: ${response.status}`);
      }

      const contentDisposition = response.headers.get('content-disposition') || '';
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
      const filename = filenameMatch?.[1] || selectedOntologyPath.split('/').pop() || 'ontology.ttl';

      const blob = await response.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      console.error('Failed to export ontology:', error);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <Header />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex h-10 items-center justify-between border-b bg-muted/30 px-4">
          <div className="flex gap-1">
            <button
              onClick={() => setViewMode('overview')}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
                viewMode === 'overview' ? 'bg-background' : 'text-muted-foreground hover:bg-background'
              )}
            >
              <Eye size={14} />
              Overview
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
              Relations
            </button>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setViewMode('import')}
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
            >
              <Upload size={14} />
              Import
            </button>
            <button
              onClick={handleExportCurrentOntology}
              disabled={!selectedOntologyPath || exporting}
              className={cn(
                "flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground",
                (!selectedOntologyPath || exporting) && "cursor-not-allowed opacity-50"
              )}
              title={!selectedOntologyPath ? 'Select an ontology file to export' : 'Export selected ontology'}
            >
              <Download size={14} />
              {exporting ? 'Exporting...' : 'Export'}
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {viewMode === 'import' && (
            <div className="flex flex-1 flex-col items-center justify-center bg-card p-8">
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

                  {/* Example paths */}
                  <div className="rounded-lg border bg-muted/30 p-4">
                    <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Example Paths
                    </p>
                    <div className="space-y-2">
                      <button
                        onClick={() => setImportPath('/Users/jrvmac/NCOR-Organization/BFO-Process-Ledger/src/ontology/bpl-modules/template/BFO7Buckets.ttl')}
                        className="block w-full rounded-md bg-background p-2 text-left text-xs font-mono hover:bg-muted"
                      >
                        BFO 7 Buckets (TTL)
                      </button>
                    </div>
                  </div>

                  {/* Supported formats */}
                  <div className="text-center text-xs text-muted-foreground">
                    Supported: .ttl (Turtle), .owl (OWL), .rdf (RDF/XML)
                  </div>
                </div>
              </div>
            </div>
          )}

          {viewMode === 'overview' && (
            <OntologyOverviewView
              ontologyPath={selectedOntologyPath}
              onCreateEntity={openCreateEntity}
              onCreateRelationship={openCreateRelationship}
            />
          )}

          {(viewMode === 'classes' || viewMode === 'relations' || viewMode === 'editor') && (
            <OntologySplitView
              mode={viewMode === 'relations' ? 'relations' : 'classes'}
              items={viewMode === 'relations' ? relationshipItems : classItems}
              selectedItem={selectedItem}
              onSelectItem={setSelectedItem}
              allClasses={allClasses}
              onUpdateItem={(itemId, updates) => updateItem(itemId, updates)}
              onCreateEntity={openCreateEntity}
              onCreateRelationship={openCreateRelationship}
            />
          )}

          {/* Create Entity Form */}
          {viewMode === 'create-entity' && (
            <div className="flex flex-1 flex-col bg-card p-6">
              <div className="mx-auto w-full max-w-2xl">
                <div className="mb-6 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Box size={24} className="text-blue-500" />
                    <h2 className="text-lg font-semibold">Create New Entity</h2>
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

                  {/* Description */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">Description</label>
                    <textarea
                      value={formDescription}
                      onChange={(e) => setFormDescription(e.target.value)}
                      placeholder="Describe what this entity represents..."
                      rows={3}
                      className="w-full resize-none rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  {/* Base Class Selector */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">
                      Map to Reference Class
                      <span className="ml-2 text-xs font-normal text-muted-foreground">(optional)</span>
                    </label>
                    
                    {referenceOntologies.length === 0 ? (
                      <div className="rounded-lg border border-dashed bg-muted/30 p-4 text-center">
                        <p className="mb-2 text-sm text-muted-foreground">No reference ontologies imported.</p>
                        <button
                          onClick={() => setViewMode('import')}
                          className="text-sm text-workspace-accent hover:underline"
                        >
                          Import a reference ontology
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {/* Selected base class display */}
                        {selectedBaseClass && (
                          <div className="flex items-center justify-between rounded-lg border bg-blue-50 dark:bg-blue-950/30 p-3">
                            <div className="flex items-center gap-2">
                              <Check size={16} className="text-blue-500" />
                              <div>
                                <p className="text-sm font-medium">{selectedBaseClass.label}</p>
                                <p className="text-xs text-muted-foreground">from {selectedBaseClass.ontologyName}</p>
                              </div>
                            </div>
                            <button
                              onClick={() => setFormBaseRef('')}
                              className="text-muted-foreground hover:text-foreground"
                            >
                              <X size={16} />
                            </button>
                          </div>
                        )}

                        {/* Search */}
                        <div className="relative">
                          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                          <input
                            type="text"
                            value={formSearchQuery}
                            onChange={(e) => setFormSearchQuery(e.target.value)}
                            placeholder="Search classes..."
                            className="w-full rounded-lg border bg-background py-2 pl-10 pr-4 text-sm outline-none focus:ring-2 focus:ring-primary"
                          />
                        </div>

                        {/* Classes grid */}
                        <div className="max-h-48 overflow-y-auto rounded-lg border bg-muted/20 p-2">
                          {filteredClasses.length === 0 ? (
                            <p className="p-2 text-center text-sm text-muted-foreground">No classes found</p>
                          ) : (
                            <div className="grid gap-1">
                              {filteredClasses.map((cls) => (
                                <button
                                  key={cls.iri}
                                  onClick={() => setFormBaseRef(cls.iri)}
                                  className={cn(
                                    'flex items-center gap-2 rounded-md p-2 text-left text-sm hover:bg-muted',
                                    formBaseRef === cls.iri && 'bg-blue-100 dark:bg-blue-900/30'
                                  )}
                                >
                                  <Box size={14} className="flex-shrink-0 text-blue-500" />
                                  <div className="flex-1 truncate">
                                    <span className="font-medium">{cls.label}</span>
                                    <span className="ml-2 text-xs text-muted-foreground">({cls.ontologyName})</span>
                                  </div>
                                  {formBaseRef === cls.iri && <Check size={14} className="text-blue-500" />}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
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
                      Create Entity
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Create Relationship Form */}
          {viewMode === 'create-relationship' && (
            <div className="flex flex-1 flex-col bg-card p-6">
              <div className="mx-auto w-full max-w-2xl">
                <div className="mb-6 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Link2 size={24} className="text-green-500" />
                    <h2 className="text-lg font-semibold">Create New Relationship</h2>
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

                  {/* Description */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">Description</label>
                    <textarea
                      value={formDescription}
                      onChange={(e) => setFormDescription(e.target.value)}
                      placeholder="Describe what this relationship represents..."
                      rows={3}
                      className="w-full resize-none rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  {/* Base Property Selector */}
                  <div>
                    <label className="mb-2 block text-sm font-medium">
                      Map to Reference Property
                      <span className="ml-2 text-xs font-normal text-muted-foreground">(optional)</span>
                    </label>
                    
                    {referenceOntologies.length === 0 ? (
                      <div className="rounded-lg border border-dashed bg-muted/30 p-4 text-center">
                        <p className="mb-2 text-sm text-muted-foreground">No reference ontologies imported.</p>
                        <button
                          onClick={() => setViewMode('import')}
                          className="text-sm text-workspace-accent hover:underline"
                        >
                          Import a reference ontology
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {/* Selected base property display */}
                        {selectedBaseProperty && (
                          <div className="flex items-center justify-between rounded-lg border bg-green-50 dark:bg-green-950/30 p-3">
                            <div className="flex items-center gap-2">
                              <Check size={16} className="text-green-500" />
                              <div>
                                <p className="text-sm font-medium">{selectedBaseProperty.label}</p>
                                <p className="text-xs text-muted-foreground">from {selectedBaseProperty.ontologyName}</p>
                              </div>
                            </div>
                            <button
                              onClick={() => setFormBaseRef('')}
                              className="text-muted-foreground hover:text-foreground"
                            >
                              <X size={16} />
                            </button>
                          </div>
                        )}

                        {/* Search */}
                        <div className="relative">
                          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                          <input
                            type="text"
                            value={formSearchQuery}
                            onChange={(e) => setFormSearchQuery(e.target.value)}
                            placeholder="Search properties..."
                            className="w-full rounded-lg border bg-background py-2 pl-10 pr-4 text-sm outline-none focus:ring-2 focus:ring-primary"
                          />
                        </div>

                        {/* Properties grid */}
                        <div className="max-h-48 overflow-y-auto rounded-lg border bg-muted/20 p-2">
                          {filteredProperties.length === 0 ? (
                            <p className="p-2 text-center text-sm text-muted-foreground">No properties found</p>
                          ) : (
                            <div className="grid gap-1">
                              {filteredProperties.map((prop) => (
                                <button
                                  key={prop.iri}
                                  onClick={() => setFormBaseRef(prop.iri)}
                                  className={cn(
                                    'flex items-center gap-2 rounded-md p-2 text-left text-sm hover:bg-muted',
                                    formBaseRef === prop.iri && 'bg-green-100 dark:bg-green-900/30'
                                  )}
                                >
                                  <Link2 size={14} className="flex-shrink-0 text-green-500" />
                                  <div className="flex-1 truncate">
                                    <span className="font-medium">{prop.label}</span>
                                    <span className="ml-2 text-xs text-muted-foreground">({prop.ontologyName})</span>
                                  </div>
                                  {formBaseRef === prop.iri && <Check size={14} className="text-green-500" />}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
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
                      Create Relationship
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

function OntologySplitView({
  mode,
  items,
  selectedItem,
  onSelectItem,
  allClasses,
  onUpdateItem,
  onCreateEntity,
  onCreateRelationship,
}: {
  mode: 'classes' | 'relations';
  items: OntologyItem[];
  selectedItem?: OntologyItem;
  onSelectItem: (itemId: string | null) => void;
  allClasses: Array<ReferenceClass & { ontologyName: string }>;
  onUpdateItem: (itemId: string, updates: Partial<OntologyItem>) => void;
  onCreateEntity: () => void;
  onCreateRelationship: () => void;
}) {
  const [query, setQuery] = useState('');
  const isClassMode = mode === 'classes';
  const modeLabel = isClassMode ? 'Classes' : 'Relations';
  const modeIcon = isClassMode ? Box : Link2;
  const ModeIcon = modeIcon;

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return items;
    return items.filter((item) => {
      return (
        item.name.toLowerCase().includes(normalizedQuery)
        || item.description?.toLowerCase().includes(normalizedQuery)
      );
    });
  }, [items, query]);

  const selectedItemInMode = selectedItem && selectedItem.type === (isClassMode ? 'entity' : 'relationship')
    ? selectedItem
    : undefined;

  return (
    <div className="flex flex-1 overflow-hidden bg-card">
      <div className="flex w-80 flex-shrink-0 flex-col border-r bg-muted/20">
        <div className="border-b p-4">
          <div className="mb-3 flex items-center gap-2">
            <ModeIcon size={18} className={isClassMode ? 'text-blue-500' : 'text-green-500'} />
            <h2 className="font-semibold">{modeLabel}</h2>
            <span className="text-xs text-muted-foreground">({items.length})</span>
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={`Search ${modeLabel.toLowerCase()}...`}
              className="w-full rounded-md border bg-background py-1.5 pl-8 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
        </div>

        <div className="flex-1 space-y-1 overflow-y-auto p-2">
          {filteredItems.length === 0 ? (
            <p className="px-2 py-4 text-center text-sm text-muted-foreground">No {modeLabel.toLowerCase()} found.</p>
          ) : (
            filteredItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelectItem(item.id)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors',
                  selectedItemInMode?.id === item.id
                    ? 'bg-workspace-accent-10 text-workspace-accent'
                    : 'hover:bg-background'
                )}
                title={item.description}
              >
                <ModeIcon size={14} className={isClassMode ? 'text-blue-500' : 'text-green-500'} />
                <span className="truncate">{item.name}</span>
              </button>
            ))
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {selectedItemInMode ? (
          <EntityDetailView
            item={selectedItemInMode}
            allClasses={allClasses}
            onUpdate={(updates) => onUpdateItem(selectedItemInMode.id, updates)}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-center">
              <div className="mb-4 flex justify-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                  <ModeIcon size={32} className={isClassMode ? 'text-blue-500' : 'text-green-500'} />
                </div>
              </div>
              <h2 className="mb-2 text-lg font-semibold">{modeLabel} Editor</h2>
              <p className="mb-6 max-w-md text-muted-foreground">
                Select a {isClassMode ? 'class' : 'relation'} from the left list or create a new {isClassMode ? 'class' : 'relation'}.
              </p>
              <div className="flex justify-center gap-3">
                <button
                  onClick={isClassMode ? onCreateEntity : onCreateRelationship}
                  className={cn(
                    'flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                    'hover:opacity-90'
                  )}
                >
                  <Plus size={16} />
                  {isClassMode ? 'Create Class' : 'Create Relationship'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

type OntologyOverviewStats = {
  name: string;
  path: string;
  ontologies_count?: number;
  classes: number;
  object_properties: number;
  data_properties: number;
  named_individuals: number;
  imports: number;
};

function OntologyOverviewView({
  ontologyPath,
  onCreateEntity,
  onCreateRelationship,
}: {
  ontologyPath: string | null;
  onCreateEntity: () => void;
  onCreateRelationship: () => void;
}) {
  const [stats, setStats] = useState<OntologyOverviewStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchStats = async () => {
      setLoadingStats(true);
      setStatsError(null);
      try {
        const baseUrl = getApiUrl();
        const statsUrl = ontologyPath
          ? `${baseUrl}/api/ontology/overview/stats?ontology_path=${encodeURIComponent(ontologyPath)}`
          : `${baseUrl}/api/ontology/overview/stats/all`;
        const response = await authFetch(
          statsUrl
        );
        if (!response.ok) {
          throw new Error(`Failed to fetch ontology stats: ${response.status}`);
        }
        const data = await response.json();
        if (!cancelled) {
          setStats(data as OntologyOverviewStats);
        }
      } catch (error) {
        if (!cancelled) {
          setStats(null);
          setStatsError('Failed to load ontology stats.');
        }
      } finally {
        if (!cancelled) {
          setLoadingStats(false);
        }
      }
    };

    fetchStats();
    return () => {
      cancelled = true;
    };
  }, [ontologyPath]);

  return (
    <div className="flex flex-1 flex-col bg-card p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Overview</h2>
          <p className="text-sm text-muted-foreground truncate" title={ontologyPath || 'All ontologies'}>
            {stats?.name || ontologyPath || 'All ontologies'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onCreateEntity}
            className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
          >
            <Box size={14} className="text-blue-500" />
            Create Entity
          </button>
          <button
            onClick={onCreateRelationship}
            className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
          >
            <Link2 size={14} className="text-green-500" />
            Create Relationship
          </button>
        </div>
      </div>

      {loadingStats && (
        <div className="flex flex-1 items-center justify-center gap-2 text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          Loading overview stats...
        </div>
      )}

      {!loadingStats && statsError && (
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300">
          {statsError}
        </div>
      )}

      {!loadingStats && !statsError && stats && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {typeof stats.ontologies_count === 'number' && (
            <div className="rounded-lg border bg-background p-4">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Ontologies</p>
              <p className="mt-1 text-2xl font-semibold">{stats.ontologies_count}</p>
            </div>
          )}
          <div className="rounded-lg border bg-background p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Classes</p>
            <p className="mt-1 text-2xl font-semibold">{stats.classes}</p>
          </div>
          <div className="rounded-lg border bg-background p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Object Properties</p>
            <p className="mt-1 text-2xl font-semibold">{stats.object_properties}</p>
          </div>
          <div className="rounded-lg border bg-background p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Data Properties</p>
            <p className="mt-1 text-2xl font-semibold">{stats.data_properties}</p>
          </div>
          <div className="rounded-lg border bg-background p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Named Individuals</p>
            <p className="mt-1 text-2xl font-semibold">{stats.named_individuals}</p>
          </div>
          <div className="rounded-lg border bg-background p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Imports</p>
            <p className="mt-1 text-2xl font-semibold">{stats.imports}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// Entity Detail View - Inspired by Palantir Foundry
const ENTITY_CENTER_SECTIONS = [
  'Overview',
  'Properties',
  'Action types',
  'Security',
  'Datasources',
  'Capabilities',
  'Object views',
  'Interfaces',
  'Automations',
  'Usage',
] as const;

const STATUS_COLORS: Record<EntityStatus, string> = {
  active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  draft: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  deprecated: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  archived: 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400',
};

const PROPERTY_TYPE_ICONS: Record<string, React.ElementType> = {
  string: Type,
  number: Hash,
  boolean: ToggleLeft,
  date: Calendar,
  datetime: Calendar,
  array: List,
  object: Box,
  reference: Link2,
};

function EntityDetailView({
  item,
  allClasses,
  onUpdate,
}: {
  item: OntologyItem;
  allClasses: Array<ReferenceClass & { ontologyName: string }>;
  onUpdate: (updates: Partial<OntologyItem>) => void;
}) {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [newAlias, setNewAlias] = useState('');
  const [showAddProperty, setShowAddProperty] = useState(false);
  const [newPropertyName, setNewPropertyName] = useState('');
  const [newPropertyType, setNewPropertyType] = useState<string>('string');

  const baseClass = allClasses.find((c) => c.iri === item.baseClass);
  const propertyCount = item.entityProperties?.length || 0;
  const additionalSectionTables = ENTITY_CENTER_SECTIONS.filter(
    (section) => !['Overview', 'Properties', 'Action types'].includes(section)
  );

  const startEdit = (field: string, value: string) => {
    setEditingField(field);
    setEditValue(value);
  };

  const saveEdit = (field: string) => {
    onUpdate({ [field]: editValue });
    setEditingField(null);
  };

  const addAlias = () => {
    if (newAlias.trim()) {
      onUpdate({ aliases: [...(item.aliases || []), newAlias.trim()] });
      setNewAlias('');
    }
  };

  const removeAlias = (alias: string) => {
    onUpdate({ aliases: (item.aliases || []).filter((a) => a !== alias) });
  };

  const addProperty = () => {
    if (newPropertyName.trim()) {
      const newProp: EntityProperty = {
        id: `prop-${Date.now()}`,
        name: newPropertyName.toLowerCase().replace(/\s+/g, '_'),
        displayName: newPropertyName.trim(),
        type: newPropertyType as EntityProperty['type'],
      };
      onUpdate({ entityProperties: [...(item.entityProperties || []), newProp] });
      setNewPropertyName('');
      setShowAddProperty(false);
    }
  };

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b bg-background px-6 py-4">
          <div className="flex items-center gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-semibold">{item.name}</h1>
                <button className="text-muted-foreground hover:text-yellow-500">
                  <Star size={18} />
                </button>
              </div>
              <p className="text-sm text-muted-foreground">
                {item.type === 'entity' ? 'Entity' : 'Relationship'} • {item.objectCount || 0} objects
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm hover:bg-muted">
              Actions
              <ChevronRight size={14} className="rotate-90" />
            </button>
            <button className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm hover:bg-muted">
              Open in
              <ChevronRight size={14} className="rotate-90" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="flex gap-6">
              {/* Main metadata */}
              <div className="flex-1 space-y-1">
                {/* Group */}
                {item.group && (
                  <div className="mb-4 flex items-center gap-2">
                    <div className="flex items-center gap-2 rounded bg-blue-100 dark:bg-blue-900/30 px-2 py-1 text-sm text-blue-700 dark:text-blue-300">
                      <LayoutGrid size={14} />
                      {item.group}
                    </div>
                    <button className="text-xs text-muted-foreground hover:underline">
                      Edit groups
                    </button>
                  </div>
                )}

                {/* Metadata table */}
                <div className="rounded-lg border divide-y">
                  {/* URIRef */}
                  <div className="flex items-center px-4 py-3">
                    <span className="w-40 text-sm text-muted-foreground">URIRef</span>
                    <span className="font-mono text-sm text-muted-foreground truncate">{item.id}</span>
                  </div>

                  {/* Inheritance */}
                  <div className="flex items-center px-4 py-3">
                    <span className="w-40 text-sm text-muted-foreground">
                      {item.type === 'relationship' ? 'Subproperty of' : 'Subclass of'}
                    </span>
                    <span className="text-sm">{item.parentName || 'None'}</span>
                  </div>

                  {/* Definition */}
                  <div className="flex items-start px-4 py-3 group">
                    <span className="w-40 text-sm text-muted-foreground">Definition</span>
                    {editingField === 'description' ? (
                      <div className="flex flex-1 items-start gap-2">
                        <textarea
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="flex-1 rounded border bg-background px-2 py-1 text-sm"
                          rows={2}
                          autoFocus
                        />
                        <div className="flex flex-col gap-1">
                          <button onClick={() => saveEdit('description')} className="text-workspace-accent">
                            <Check size={16} />
                          </button>
                          <button onClick={() => setEditingField(null)} className="text-muted-foreground">
                            <X size={16} />
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-1 items-start justify-between">
                        <span className="text-sm">{item.description || 'No description'}</span>
                        <button
                          onClick={() => startEdit('description', item.description || '')}
                          className="text-muted-foreground opacity-0 hover:text-foreground group-hover:opacity-100"
                        >
                          <Pencil size={14} />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Example */}
                  <div className="flex items-center px-4 py-3">
                    <span className="w-40 text-sm text-muted-foreground">Example</span>
                    <span className="text-sm">{baseClass?.examples || 'No example'}</span>
                  </div>

                  {/* Aliases */}
                  <div className="flex items-center px-4 py-3">
                    <span className="flex w-40 items-center gap-1 text-sm text-muted-foreground">
                      Aliases
                      <HelpCircle size={12} />
                    </span>
                    <div className="flex flex-1 flex-wrap items-center gap-2">
                      {(item.aliases || []).map((alias) => (
                        <span
                          key={alias}
                          className="flex items-center gap-1 rounded bg-muted px-2 py-0.5 text-sm"
                        >
                          {alias}
                          <button
                            onClick={() => removeAlias(alias)}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                      <div className="flex items-center gap-1">
                        <input
                          type="text"
                          value={newAlias}
                          onChange={(e) => setNewAlias(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && addAlias()}
                          placeholder="Add alias..."
                          className="w-24 rounded border bg-background px-2 py-0.5 text-sm"
                        />
                        {newAlias && (
                          <button onClick={addAlias} className="text-workspace-accent">
                            <Plus size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Point of contact */}
                  <div className="flex items-center px-4 py-3">
                    <span className="flex w-40 items-center gap-1 text-sm text-muted-foreground">
                      Point of contact
                      <HelpCircle size={12} />
                    </span>
                    <div className="flex flex-1 items-center justify-between">
                      <span className="text-sm">{item.pointOfContact || 'None'}</span>
                      <div className="flex items-center gap-2">
                        {item.pointOfContact && (
                          <button className="text-muted-foreground hover:text-foreground">
                            <Mail size={14} />
                          </button>
                        )}
                        <button className="text-muted-foreground hover:text-foreground">
                          <Pencil size={14} />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Contributors */}
                  <div className="flex items-center px-4 py-3">
                    <span className="w-40 text-sm text-muted-foreground">Contributors</span>
                    <span className="text-sm">{item.contributors?.join(', ') || 'None'}</span>
                  </div>

                </div>

                {/* Properties Section */}
                <div className="mt-6 rounded-lg border">
                  <div className="flex items-center justify-between border-b px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Properties</span>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{propertyCount}</span>
                    </div>
                    <button
                      onClick={() => setShowAddProperty(true)}
                      className="flex items-center gap-1 text-sm text-workspace-accent hover:underline"
                    >
                      <Plus size={14} />
                      New
                    </button>
                  </div>
                  <div className="divide-y">
                    {(item.entityProperties || []).map((prop) => {
                      const TypeIcon = PROPERTY_TYPE_ICONS[prop.type] || Type;
                      return (
                        <div key={prop.id} className="flex items-center px-4 py-2">
                          <TypeIcon size={14} className="mr-2 text-muted-foreground" />
                          <span className="flex-1 text-sm">{prop.displayName}</span>
                          {prop.isTitle && (
                            <span className="mr-2 rounded bg-blue-100 dark:bg-blue-900/30 px-1.5 py-0.5 text-xs text-blue-700 dark:text-blue-300">
                              Title
                            </span>
                          )}
                          {prop.isPrimaryKey && (
                            <span className="mr-2 rounded bg-purple-100 dark:bg-purple-900/30 px-1.5 py-0.5 text-xs text-purple-700 dark:text-purple-300">
                              Primary key
                            </span>
                          )}
                        </div>
                      );
                    })}
                    {propertyCount === 0 && (
                      <div className="px-4 py-4 text-center text-sm text-muted-foreground">
                        No properties defined yet
                      </div>
                    )}
                  </div>
                  {showAddProperty && (
                    <div className="border-t p-4">
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={newPropertyName}
                          onChange={(e) => setNewPropertyName(e.target.value)}
                          placeholder="Property name"
                          className="flex-1 rounded border bg-background px-3 py-1.5 text-sm"
                          autoFocus
                        />
                        <select
                          value={newPropertyType}
                          onChange={(e) => setNewPropertyType(e.target.value)}
                          className="rounded border bg-background px-3 py-1.5 text-sm"
                        >
                          <option value="string">String</option>
                          <option value="number">Number</option>
                          <option value="boolean">Boolean</option>
                          <option value="date">Date</option>
                          <option value="datetime">DateTime</option>
                          <option value="array">Array</option>
                          <option value="reference">Reference</option>
                        </select>
                        <button
                          onClick={addProperty}
                          disabled={!newPropertyName.trim()}
                          className="rounded bg-workspace-accent px-3 py-1.5 text-sm text-white disabled:opacity-50"
                        >
                          Add
                        </button>
                        <button
                          onClick={() => {
                            setShowAddProperty(false);
                            setNewPropertyName('');
                          }}
                          className="text-muted-foreground"
                        >
                          <X size={18} />
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Actions Section */}
                <div className="mt-6 rounded-lg border">
                  <div className="flex items-center justify-between border-b px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Action types</span>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs">
                        {item.actions?.length || 0}
                      </span>
                    </div>
                    <button className="flex items-center gap-1 text-sm text-workspace-accent hover:underline">
                      <Plus size={14} />
                      New
                    </button>
                  </div>
                  <div className="p-4">
                    {(item.actions || []).length === 0 ? (
                      <p className="text-center text-sm text-muted-foreground">
                        No actions defined yet
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {(item.actions || []).map((action) => (
                          <div
                            key={action.id}
                            className="flex items-center gap-2 rounded border bg-muted/30 p-2"
                          >
                            <Pencil size={14} className="text-blue-500" />
                            <span className="text-sm">{action.name}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {additionalSectionTables.map((section) => (
                  <div key={section} className="mt-6 rounded-lg border">
                    <div className="flex items-center justify-between border-b px-4 py-3">
                      <span className="font-medium">{section}</span>
                    </div>
                    <div className="p-4 text-sm text-muted-foreground">
                      No {section.toLowerCase()} configured yet
                    </div>
                  </div>
                ))}
              </div>

              {/* Right Status Panel */}
              <div className="w-64 flex-shrink-0 space-y-4">
                {/* Status */}
                <div className="rounded-lg border p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Status</span>
                    <select
                      value={item.status || 'draft'}
                      onChange={(e) => onUpdate({ status: e.target.value as EntityStatus })}
                      className={cn(
                        'rounded px-2 py-0.5 text-sm font-medium',
                        STATUS_COLORS[item.status || 'draft']
                      )}
                    >
                      <option value="active">Active</option>
                      <option value="draft">Draft</option>
                      <option value="deprecated">Deprecated</option>
                      <option value="archived">Archived</option>
                    </select>
                  </div>
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Visibility</span>
                    <select
                      value={item.visibility || 'normal'}
                      onChange={(e) => onUpdate({ visibility: e.target.value as EntityVisibility })}
                      className="rounded border bg-background px-2 py-0.5 text-sm"
                    >
                      <option value="normal">Normal</option>
                      <option value="hidden">Hidden</option>
                      <option value="internal">Internal</option>
                    </select>
                  </div>
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Index status</span>
                    <span className="text-sm text-orange-500">Not indexed</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Edits</span>
                    <span className="rounded bg-muted px-2 py-0.5 text-sm">Enabled</span>
                  </div>
                </div>

              </div>
            </div>
        </div>
      </div>
    </div>
  );
}
