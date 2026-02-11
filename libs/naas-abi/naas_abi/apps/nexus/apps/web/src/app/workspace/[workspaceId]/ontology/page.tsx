'use client';

import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  Network,
  Plus,
  FileCode,
  Eye,
  Download,
  Upload,
  FolderOpen,
  X,
  BookOpen,
  Box,
  Link2,
  ChevronRight,
  Trash2,
  Loader2,
  Check,
  Search,
  Star,
  MoreHorizontal,
  ExternalLink,
  Mail,
  Pencil,
  Shield,
  Database,
  Zap,
  LayoutGrid,
  Settings,
  BarChart3,
  Users,
  Key,
  Type,
  Hash,
  Calendar,
  ToggleLeft,
  List,
  HelpCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOntologyStore, type ReferenceOntology, type ReferenceClass, type ReferenceProperty, type OntologyItem, type EntityProperty, type EntityStatus, type EntityVisibility } from '@/stores/ontology';

type ViewMode = 'editor' | 'import' | 'references' | 'create-entity' | 'create-relationship';

export default function OntologyPage() {
  const searchParams = useSearchParams();
  const initialView = (searchParams.get('view') as ViewMode) || 'editor';
  
  const [viewMode, setViewMode] = useState<ViewMode>(initialView);
  const [importPath, setImportPath] = useState('');
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  
  // Creation form state
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formBaseRef, setFormBaseRef] = useState<string>(''); // IRI of selected base class/property
  const [formSearchQuery, setFormSearchQuery] = useState('');
  const [creating, setCreating] = useState(false);
  
  // Update view mode and pre-fill form when URL changes
  useEffect(() => {
    const view = searchParams.get('view') as ViewMode;
    if (view && ['editor', 'import', 'references', 'create-entity', 'create-relationship'].includes(view)) {
      setViewMode(view);
      
      // Pre-fill base class/property from URL if provided
      const baseClass = searchParams.get('baseClass');
      const baseProperty = searchParams.get('baseProperty');
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
    removeReferenceOntology,
    createEntity,
    createRelationship,
    setSelectedItem,
    updateItem,
  } = useOntologyStore();

  const selectedItem = items.find((i) => i.id === selectedItemId);

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
        setViewMode('references');
      } else {
        setImportError('Failed to import ontology. Check the file path.');
      }
    } catch (err) {
      setImportError('Error importing ontology');
    } finally {
      setImporting(false);
    }
  };

  const handleCreateFromClass = (cls: { label: string; definition?: string; iri: string }) => {
    // Pre-fill form and open create-entity view
    setFormName('');
    setFormDescription(cls.definition || '');
    setFormBaseRef(cls.iri);
    setViewMode('create-entity');
  };

  const resetForm = () => {
    setFormName('');
    setFormDescription('');
    setFormBaseRef('');
    setFormSearchQuery('');
  };

  const openCreateEntity = () => {
    resetForm();
    setViewMode('create-entity');
  };

  const openCreateRelationship = () => {
    resetForm();
    setViewMode('create-relationship');
  };

  const handleSubmitEntity = async () => {
    if (!formName.trim()) return;
    setCreating(true);
    try {
      await createEntity(formName.trim(), formDescription.trim() || undefined, formBaseRef || undefined);
      resetForm();
      setViewMode('editor');
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
      setViewMode('editor');
    } finally {
      setCreating(false);
    }
  };

  const selectedBaseClass = allClasses.find((c) => c.iri === formBaseRef);
  const selectedBaseProperty = allProperties.find((p) => p.iri === formBaseRef);

  return (
    <div className="flex h-full flex-col">
      <Header />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex h-10 items-center justify-between border-b bg-muted/30 px-4">
          <div className="flex gap-1">
            <button
              onClick={() => setViewMode('editor')}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
                viewMode === 'editor' ? 'bg-background' : 'text-muted-foreground hover:bg-background'
              )}
            >
              <FileCode size={14} />
              Editor
            </button>
            <button
              onClick={() => setViewMode('import')}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
                viewMode === 'import' ? 'bg-background' : 'text-muted-foreground hover:bg-background'
              )}
            >
              <Upload size={14} />
              Import
            </button>
            <button
              onClick={() => setViewMode('references')}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
                viewMode === 'references' ? 'bg-background' : 'text-muted-foreground hover:bg-background'
              )}
            >
              <BookOpen size={14} />
              References ({referenceOntologies.length})
            </button>
          </div>
          <button className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            <Download size={14} />
            Export
          </button>
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

          {viewMode === 'references' && (
            <div className="flex flex-1 flex-col bg-card p-6">
              <div className="mb-6">
                <h2 className="text-lg font-semibold">Reference Ontologies</h2>
                <p className="text-sm text-muted-foreground">
                  Imported ontologies you can use as templates when creating entities.
                </p>
              </div>

              {referenceOntologies.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center">
                  <BookOpen size={48} className="mb-4 text-muted-foreground/50" />
                  <p className="mb-4 text-muted-foreground">No reference ontologies imported yet.</p>
                  <button
                    onClick={() => setViewMode('import')}
                    className="flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
                  >
                    <Upload size={16} />
                    Import Ontology
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {referenceOntologies.map((ref) => (
                    <ReferenceCard
                      key={ref.id}
                      reference={ref}
                      onRemove={() => removeReferenceOntology(ref.id)}
                      onCreateFromClass={handleCreateFromClass}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {viewMode === 'editor' && (
            <div className="flex flex-1 overflow-hidden bg-card">
              {selectedItem ? (
                <EntityDetailView 
                  item={selectedItem} 
                  allClasses={allClasses}
                  onUpdate={(updates) => updateItem(selectedItem.id, updates)}
                />
              ) : (
                <div className="flex flex-1 items-center justify-center">
                  <div className="text-center">
                    <div className="mb-4 flex justify-center">
                      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                        <Network size={32} className="text-muted-foreground" />
                      </div>
                    </div>
                    <h2 className="mb-2 text-lg font-semibold">Ontology Editor</h2>
                    <p className="mb-6 max-w-md text-muted-foreground">
                      Define classes, properties, and relations. Import reference ontologies to use as templates.
                    </p>
                    <div className="flex justify-center gap-3">
                      <button
                        onClick={() => setViewMode('import')}
                        className="flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                      >
                        <Upload size={16} />
                        Import Reference
                      </button>
                      <button
                        onClick={openCreateEntity}
                        className={cn(
                          'flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                          'hover:opacity-90'
                        )}
                      >
                        <Plus size={16} />
                        Create Entity
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
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
                    onClick={() => setViewMode('editor')}
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
                      onClick={() => setViewMode('editor')}
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
                    onClick={() => setViewMode('editor')}
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
                      onClick={() => setViewMode('editor')}
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

function ReferenceCard({
  reference,
  onRemove,
  onCreateFromClass,
}: {
  reference: ReferenceOntology;
  onRemove: () => void;
  onCreateFromClass: (cls: { label: string; definition?: string; iri: string }) => void;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="rounded-lg border bg-background">
      <div className="flex items-center justify-between p-4">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-3"
        >
          <ChevronRight
            size={16}
            className={cn('transition-transform', expanded && 'rotate-90')}
          />
          <BookOpen size={20} className="text-amber-500" />
          <div className="text-left">
            <h3 className="font-medium">{reference.name}</h3>
            <p className="text-xs text-muted-foreground">
              {reference.classes.length} classes • {reference.properties.length} properties
            </p>
          </div>
        </button>
        <button
          onClick={onRemove}
          className="rounded p-2 text-muted-foreground hover:bg-muted hover:text-red-500"
          title="Remove reference"
        >
          <Trash2 size={16} />
        </button>
      </div>

      {expanded && (
        <div className="border-t p-4">
          <div className="mb-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Classes
            </p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {reference.classes.map((cls) => (
                <button
                  key={cls.iri}
                  onClick={() => onCreateFromClass(cls)}
                  className="flex items-center gap-2 rounded-md border bg-muted/30 p-2 text-left text-sm hover:bg-muted"
                  title={cls.definition || cls.iri}
                >
                  <Box size={14} className="flex-shrink-0 text-blue-500" />
                  <span className="truncate">{cls.label}</span>
                  <Plus size={12} className="ml-auto flex-shrink-0 text-muted-foreground" />
                </button>
              ))}
            </div>
          </div>

          {reference.properties.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Properties
              </p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {reference.properties.slice(0, 9).map((prop) => (
                  <div
                    key={prop.iri}
                    className="flex items-center gap-2 rounded-md border bg-muted/30 p-2 text-sm"
                    title={prop.definition || prop.iri}
                  >
                    <Link2 size={14} className="flex-shrink-0 text-green-500" />
                    <span className="truncate">{prop.label}</span>
                  </div>
                ))}
                {reference.properties.length > 9 && (
                  <div className="flex items-center justify-center rounded-md border bg-muted/30 p-2 text-sm text-muted-foreground">
                    +{reference.properties.length - 9} more
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Entity Detail View - Inspired by Palantir Foundry
type EntityTab = 'overview' | 'properties' | 'security' | 'datasources' | 'capabilities' | 'views' | 'interfaces' | 'automations' | 'usage';

const ENTITY_TABS: { id: EntityTab; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutGrid },
  { id: 'properties', label: 'Properties', icon: List },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'datasources', label: 'Datasources', icon: Database },
  { id: 'capabilities', label: 'Capabilities', icon: Zap },
  { id: 'views', label: 'Object views', icon: LayoutGrid },
  { id: 'interfaces', label: 'Interfaces', icon: Settings },
  { id: 'automations', label: 'Automations', icon: Zap },
  { id: 'usage', label: 'Usage', icon: BarChart3 },
];

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
  const [activeTab, setActiveTab] = useState<EntityTab>('overview');
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [newAlias, setNewAlias] = useState('');
  const [showAddProperty, setShowAddProperty] = useState(false);
  const [newPropertyName, setNewPropertyName] = useState('');
  const [newPropertyType, setNewPropertyType] = useState<string>('string');

  const baseClass = allClasses.find((c) => c.iri === item.baseClass);
  const propertyCount = item.entityProperties?.length || 0;

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

  const togglePropertyFlag = (propId: string, flag: 'isPrimaryKey' | 'isTitle') => {
    const updated = (item.entityProperties || []).map((p) => {
      if (p.id === propId) {
        return { ...p, [flag]: !p[flag] };
      }
      // If setting as primary key or title, remove from others
      if (flag === 'isPrimaryKey' || flag === 'isTitle') {
        return { ...p, [flag]: false };
      }
      return p;
    });
    // Set the flag on the target property
    const final = updated.map((p) => (p.id === propId ? { ...p, [flag]: !item.entityProperties?.find((ep) => ep.id === propId)?.[flag] } : p));
    onUpdate({ entityProperties: final });
  };

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Left Navigation */}
      <div className="flex w-56 flex-shrink-0 flex-col border-r bg-muted/20">
        {/* Entity info */}
        <div className="border-b p-4">
          <div className="mb-2 flex items-center gap-2">
            <Box size={20} className="text-blue-500" />
            <span className="font-medium truncate">{item.name}</span>
            {item.status === 'active' && (
              <div className="ml-auto h-2 w-2 rounded-full bg-green-500" title="Active" />
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {item.objectCount || 0} objects
          </p>
        </div>

        {/* Tabs */}
        <nav className="flex-1 overflow-y-auto p-2">
          {ENTITY_TABS.map((tab) => {
            const Icon = tab.icon;
            const count = tab.id === 'properties' ? propertyCount : undefined;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                  activeTab === tab.id
                    ? 'bg-workspace-accent-10 text-workspace-accent font-medium'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                <Icon size={16} />
                <span className="flex-1 text-left">{tab.label}</span>
                {count !== undefined && (
                  <span className="text-xs">{count}</span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b bg-background px-6 py-4">
          <div className="flex items-center gap-3">
            <Box size={28} className="text-blue-500" />
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
          {activeTab === 'overview' && (
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
                  {/* Plural name */}
                  <div className="flex items-center px-4 py-3">
                    <span className="w-40 text-sm text-muted-foreground">Plural name</span>
                    {editingField === 'pluralName' ? (
                      <div className="flex flex-1 items-center gap-2">
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="flex-1 rounded border bg-background px-2 py-1 text-sm"
                          autoFocus
                        />
                        <button onClick={() => saveEdit('pluralName')} className="text-workspace-accent">
                          <Check size={16} />
                        </button>
                        <button onClick={() => setEditingField(null)} className="text-muted-foreground">
                          <X size={16} />
                        </button>
                      </div>
                    ) : (
                      <div className="flex flex-1 items-center justify-between">
                        <span className="text-sm">{item.pluralName || `${item.name}s`}</span>
                        <button
                          onClick={() => startEdit('pluralName', item.pluralName || `${item.name}s`)}
                          className="text-muted-foreground opacity-0 hover:text-foreground group-hover:opacity-100"
                        >
                          <Pencil size={14} />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Description */}
                  <div className="flex items-start px-4 py-3 group">
                    <span className="w-40 text-sm text-muted-foreground">Description</span>
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

                  {/* Base class / Ontology */}
                  <div className="flex items-center px-4 py-3">
                    <span className="w-40 text-sm text-muted-foreground">Base class</span>
                    <span className="text-sm">
                      {baseClass ? (
                        <span className="flex items-center gap-1">
                          <Box size={12} className="text-blue-500" />
                          {baseClass.label}
                          <span className="text-muted-foreground">({baseClass.ontologyName})</span>
                        </span>
                      ) : (
                        'None'
                      )}
                    </span>
                  </div>

                  {/* API name */}
                  <div className="flex items-center px-4 py-3">
                    <span className="w-40 text-sm text-muted-foreground">API name</span>
                    <span className="font-mono text-sm text-muted-foreground truncate">
                      {item.apiName || item.id}
                    </span>
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

                {/* IDs */}
                <div className="rounded-lg border p-4">
                  <div className="mb-3">
                    <span className="text-sm text-muted-foreground">ID</span>
                    <p className="truncate font-mono text-xs">{item.id}</p>
                  </div>
                  {item.apiName && (
                    <div>
                      <span className="text-sm text-muted-foreground">API Name</span>
                      <p className="truncate font-mono text-xs">{item.apiName}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'properties' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Properties</h2>
                <button
                  onClick={() => setShowAddProperty(true)}
                  className="flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
                >
                  <Plus size={16} />
                  Add Property
                </button>
              </div>
              <div className="rounded-lg border divide-y">
                {(item.entityProperties || []).map((prop) => {
                  const TypeIcon = PROPERTY_TYPE_ICONS[prop.type] || Type;
                  return (
                    <div key={prop.id} className="flex items-center p-4">
                      <TypeIcon size={18} className="mr-3 text-muted-foreground" />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{prop.displayName}</span>
                          {prop.isTitle && (
                            <span className="rounded bg-blue-100 dark:bg-blue-900/30 px-1.5 py-0.5 text-xs text-blue-700 dark:text-blue-300">
                              Title
                            </span>
                          )}
                          {prop.isPrimaryKey && (
                            <span className="rounded bg-purple-100 dark:bg-purple-900/30 px-1.5 py-0.5 text-xs text-purple-700 dark:text-purple-300">
                              Primary key
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {prop.type} • {prop.name}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => togglePropertyFlag(prop.id, 'isTitle')}
                          className={cn(
                            'rounded px-2 py-1 text-xs',
                            prop.isTitle ? 'bg-blue-100 text-blue-700' : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          )}
                        >
                          Title
                        </button>
                        <button
                          onClick={() => togglePropertyFlag(prop.id, 'isPrimaryKey')}
                          className={cn(
                            'rounded px-2 py-1 text-xs',
                            prop.isPrimaryKey ? 'bg-purple-100 text-purple-700' : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          )}
                        >
                          <Key size={12} />
                        </button>
                      </div>
                    </div>
                  );
                })}
                {propertyCount === 0 && (
                  <div className="p-8 text-center">
                    <List size={32} className="mx-auto mb-2 text-muted-foreground" />
                    <p className="text-muted-foreground">No properties defined yet</p>
                    <button
                      onClick={() => setShowAddProperty(true)}
                      className="mt-2 text-sm text-workspace-accent hover:underline"
                    >
                      Add your first property
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab !== 'overview' && activeTab !== 'properties' && (
            <div className="flex flex-1 flex-col items-center justify-center py-12">
              <div className="rounded-2xl bg-muted p-4">
                {activeTab === 'security' && <Shield size={32} className="text-muted-foreground" />}
                {activeTab === 'datasources' && <Database size={32} className="text-muted-foreground" />}
                {activeTab === 'capabilities' && <Zap size={32} className="text-muted-foreground" />}
                {activeTab === 'views' && <LayoutGrid size={32} className="text-muted-foreground" />}
                {activeTab === 'interfaces' && <Settings size={32} className="text-muted-foreground" />}
                {activeTab === 'automations' && <Zap size={32} className="text-muted-foreground" />}
                {activeTab === 'usage' && <BarChart3 size={32} className="text-muted-foreground" />}
              </div>
              <h3 className="mt-4 text-lg font-medium capitalize">{activeTab}</h3>
              <p className="mt-1 text-muted-foreground">Coming soon</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
