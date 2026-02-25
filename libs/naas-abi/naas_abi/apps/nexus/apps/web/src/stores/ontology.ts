'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { useWorkspaceStore } from './workspace';
import { getApiUrl } from '@/lib/config';
import { authFetch } from './auth';

// Helper to get current workspace ID
const getCurrentWorkspaceId = () => useWorkspaceStore.getState().currentWorkspaceId;

export type OntologyItemType = 'entity' | 'relationship' | 'schema' | 'folder';
export type PropertyType = 'string' | 'number' | 'boolean' | 'date' | 'datetime' | 'array' | 'object' | 'reference';
export type EntityStatus = 'active' | 'draft' | 'deprecated' | 'archived';
export type EntityVisibility = 'normal' | 'hidden' | 'internal';

export interface EntityProperty {
  id: string;
  name: string;
  displayName: string;
  type: PropertyType;
  required?: boolean;
  isPrimaryKey?: boolean;
  isTitle?: boolean;
  description?: string;
  defaultValue?: unknown;
  referenceType?: string; // For reference properties
}

export interface EntityAction {
  id: string;
  name: string;
  description?: string;
  icon?: string;
}

export interface OntologyItem {
  id: string;
  workspaceId: string; // Workspace this item belongs to
  name: string;
  type: OntologyItemType;
  description?: string;
  parentId?: string; // for folder hierarchy
  
  // Extended metadata (inspired by Palantir Foundry)
  pluralName?: string;
  aliases?: string[];
  group?: string;
  pointOfContact?: string;
  contributors?: string[];
  status?: EntityStatus;
  visibility?: EntityVisibility;
  apiName?: string;
  
  // Properties for entities
  entityProperties?: EntityProperty[];
  
  // Actions that can be performed on this entity
  actions?: EntityAction[];
  
  // For items based on reference ontologies
  baseClass?: string; // IRI of the base class
  parentName?: string;
  referenceOntologyId?: string;
  
  // Metadata
  objectCount?: number; // Number of instances
  createdAt: Date;
  updatedAt: Date;
}

// Reference ontology types
export interface ReferenceClass {
  iri: string;
  label: string;
  definition?: string;
  examples?: string;
  subClassOf?: string[];
}

export interface ReferenceProperty {
  iri: string;
  label: string;
  definition?: string;
  inverseOf?: string;
  domain?: string[];
  range?: string[];
}

export interface ReferenceOntology {
  id: string;
  name: string;
  filePath: string;
  format: 'ttl' | 'owl' | 'rdf' | 'yaml';
  classes: ReferenceClass[];
  properties: ReferenceProperty[];
  importedAt: Date;
}

interface OntologyState {
  // User's items
  items: OntologyItem[];
  loading: boolean;
  error: string | null;
  
  // Reference ontologies
  referenceOntologies: ReferenceOntology[];
  loadingReference: boolean;
  expandedReferences: string[]; // IDs of expanded reference ontologies
  
  // Selection
  selectedItemId: string | null;
  expandedFolders: string[];
  
  // Actions
  setItems: (items: OntologyItem[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSelectedItem: (id: string | null) => void;
  toggleFolder: (id: string) => void;
  toggleReference: (id: string) => void;
  
  // CRUD for user items
  fetchItems: () => Promise<void>;
  fetchItemsForView: (view: 'classes' | 'relations', ontologyPath?: string | null) => Promise<void>;
  createEntity: (name: string, description?: string, baseClass?: string) => Promise<OntologyItem | null>;
  createRelationship: (name: string, description?: string, baseProperty?: string) => Promise<OntologyItem | null>;
  createFolder: (name: string) => Promise<OntologyItem | null>;
  deleteItem: (id: string) => Promise<boolean>;
  updateItem: (id: string, updates: Partial<OntologyItem>) => Promise<boolean>;
  refreshItems: () => Promise<void>;
  
  // Reference ontology actions
  importReferenceOntology: (filePath: string) => Promise<ReferenceOntology | null>;
  removeReferenceOntology: (id: string) => void;
  parseOntologyFile: (content: string, format: string, filePath: string) => ReferenceOntology;
  
  // Workspace scoping
  getWorkspaceItems: () => OntologyItem[];
}

// Simple TTL parser for extracting classes and properties
function parseTTL(content: string, filePath: string): ReferenceOntology {
  const classes: ReferenceClass[] = [];
  const properties: ReferenceProperty[] = [];
  
  // Extract prefixes
  const prefixes: Record<string, string> = {};
  const prefixRegex = /@prefix\s+(\w+):\s+<([^>]+)>\s*\./g;
  let match;
  while ((match = prefixRegex.exec(content)) !== null) {
    prefixes[match[1]] = match[2];
  }
  
  // Find classes (owl:Class)
  const classRegex = /<([^>]+)>\s+a\s+owl:Class\s*;([^.]+)\./gs;
  while ((match = classRegex.exec(content)) !== null) {
    const iri = match[1];
    const body = match[2];
    
    // Extract label
    const labelMatch = body.match(/rdfs:label\s+"([^"]+)"(@\w+)?/);
    const label = labelMatch ? labelMatch[1] : iri.split('/').pop() || iri;
    
    // Extract definition
    const defMatch = body.match(/skos:definition\s+"([^"]+)"(@\w+)?/);
    const definition = defMatch ? defMatch[1] : undefined;
    
    // Extract examples
    const exampleMatch = body.match(/skos:example\s+"([^"]+)"(@\w+)?/);
    const examples = exampleMatch ? exampleMatch[1] : undefined;
    
    classes.push({ iri, label, definition, examples });
  }
  
  // Find object properties
  const propRegex = /<([^>]+)>\s+rdf:type\s+owl:ObjectProperty\s*;?([^.]*)\./gs;
  while ((match = propRegex.exec(content)) !== null) {
    const iri = match[1];
    const body = match[2];
    
    // Extract label
    const labelMatch = body.match(/rdfs:label\s+"([^"]+)"(@\w+)?/);
    const label = labelMatch ? labelMatch[1] : iri.split('/').pop() || iri;
    
    // Extract definition
    const defMatch = body.match(/skos:definition\s+"([^"]+)"(@\w+)?/);
    const definition = defMatch ? defMatch[1] : undefined;
    
    properties.push({ iri, label, definition });
  }
  
  // Extract ontology name
  const nameMatch = content.match(/dc:title\s+"([^"]+)"(@\w+)?/);
  const name = nameMatch ? nameMatch[1] : filePath.split('/').pop()?.replace('.ttl', '') || 'Imported Ontology';
  
  return {
    id: `ref-${Date.now()}`,
    name,
    filePath,
    format: 'ttl',
    classes,
    properties,
    importedAt: new Date(),
  };
}

export const useOntologyStore = create<OntologyState>()(
  persist(
    (set, get) => ({
      items: [],
      loading: false,
      error: null,
      selectedItemId: null,
      expandedFolders: [],
      referenceOntologies: [],
      loadingReference: false,
      expandedReferences: [],

      setItems: (items) => set({ items }),
      setLoading: (loading) => set({ loading }),
      setError: (error) => set({ error }),
      setSelectedItem: (id) => set({ selectedItemId: id }),
      
      toggleFolder: (id) => set((state) => ({
        expandedFolders: state.expandedFolders.includes(id)
          ? state.expandedFolders.filter((f) => f !== id)
          : [...state.expandedFolders, id],
      })),
      
      toggleReference: (id) => set((state) => ({
        expandedReferences: state.expandedReferences.includes(id)
          ? state.expandedReferences.filter((r) => r !== id)
          : [...state.expandedReferences, id],
      })),

      fetchItems: async () => {
        set({ loading: true, error: null });
        try {
          const baseUrl = getApiUrl();
          const workspaceId = getCurrentWorkspaceId() || 'default';
          const [classesResponse, relationshipsResponse] = await Promise.all([
            authFetch(`${baseUrl}/api/ontology/classes`),
            authFetch(`${baseUrl}/api/ontology/relationships`),
          ]);

          if (!classesResponse.ok) {
            throw new Error(`Failed to fetch classes: ${classesResponse.status}`);
          }
          if (!relationshipsResponse.ok) {
            throw new Error(`Failed to fetch relationships: ${relationshipsResponse.status}`);
          }

          const classesData = await classesResponse.json();
          const relationshipsData = await relationshipsResponse.json();

          const normalizeItems = (rawItems: unknown): OntologyItem[] => {
            const sourceItems = Array.isArray(rawItems)
              ? rawItems
              : (rawItems as { items?: unknown[] })?.items || [];

            return sourceItems.map((item) => {
              const typedItem = item as Partial<OntologyItem> & {
                base_class?: string;
                parent_id?: string;
                parent_name?: string;
                sub_class_of?: string;
                sub_property_of?: string;
                subClassOf?: string;
                subPropertyOf?: string;
                created_at?: string;
                updated_at?: string;
              };
              return {
                ...typedItem,
                workspaceId: typedItem.workspaceId || workspaceId,
                parentId: typedItem.parentId || typedItem.parent_id,
                parentName: typedItem.parentName || typedItem.parent_name,
                baseClass:
                  typedItem.baseClass ||
                  typedItem.base_class ||
                  typedItem.parentId ||
                  typedItem.parent_id ||
                  typedItem.subClassOf ||
                  typedItem.sub_class_of ||
                  typedItem.subPropertyOf ||
                  typedItem.sub_property_of,
                createdAt: typedItem.createdAt ? new Date(typedItem.createdAt) : (
                  typedItem.created_at ? new Date(typedItem.created_at) : new Date()
                ),
                updatedAt: typedItem.updatedAt ? new Date(typedItem.updatedAt) : (
                  typedItem.updated_at ? new Date(typedItem.updated_at) : new Date()
                ),
              } as OntologyItem;
            });
          };

          const fetchedItems = [
            ...normalizeItems(classesData),
            ...normalizeItems(relationshipsData),
          ];
          const localFolders = get().items.filter((item) => item.type === 'folder');
          const mergedItems = [...fetchedItems, ...localFolders];
          const sortedItems = mergedItems.sort((a, b) =>
            (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' })
          );
          set({ items: sortedItems, loading: false });
        } catch (err) {
          console.error('Failed to fetch ontology:', err);
          set({ 
            items: [],
            loading: false,
            error: null,
          });
        }
      },

      fetchItemsForView: async (view, ontologyPath) => {
        set({ loading: true, error: null });
        try {
          const baseUrl = getApiUrl();
          const workspaceId = getCurrentWorkspaceId() || 'default';
          const isClassesView = view === 'classes';
          const pathSuffix = isClassesView ? '/api/ontology/classes' : '/api/ontology/relationships';
          const query = ontologyPath
            ? `?ontology_path=${encodeURIComponent(ontologyPath)}`
            : '';
          const response = await authFetch(
            `${baseUrl}${pathSuffix}${query}`
          );

          if (!response.ok) {
            throw new Error(`Failed to fetch ${view}: ${response.status}`);
          }

          const data = await response.json();
          const sourceItems = Array.isArray(data)
            ? data
            : (data as { items?: unknown[] })?.items || [];
          const expectedType: OntologyItemType = isClassesView ? 'entity' : 'relationship';

          const normalizedItems = sourceItems.map((item) => {
            const typedItem = item as Partial<OntologyItem> & {
              base_class?: string;
              parent_id?: string;
              parent_name?: string;
              sub_class_of?: string;
              sub_property_of?: string;
              subClassOf?: string;
              subPropertyOf?: string;
              created_at?: string;
              updated_at?: string;
            };
            return {
              ...typedItem,
              type: expectedType,
              workspaceId: typedItem.workspaceId || workspaceId,
              parentId: typedItem.parentId || typedItem.parent_id,
              parentName: typedItem.parentName || typedItem.parent_name,
              baseClass:
                typedItem.baseClass ||
                typedItem.base_class ||
                typedItem.parentId ||
                typedItem.parent_id ||
                typedItem.subClassOf ||
                typedItem.sub_class_of ||
                typedItem.subPropertyOf ||
                typedItem.sub_property_of,
              createdAt: typedItem.createdAt ? new Date(typedItem.createdAt) : (
                typedItem.created_at ? new Date(typedItem.created_at) : new Date()
              ),
              updatedAt: typedItem.updatedAt ? new Date(typedItem.updatedAt) : (
                typedItem.updated_at ? new Date(typedItem.updated_at) : new Date()
              ),
            } as OntologyItem;
          });

          set((state) => {
            const preservedItems = state.items.filter((item) =>
              isClassesView ? item.type !== 'entity' : item.type !== 'relationship'
            );
            const mergedItems = [...preservedItems, ...normalizedItems].sort((a, b) =>
              (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' })
            );
            return { items: mergedItems, loading: false };
          });
        } catch (err) {
          console.error(`Failed to fetch ${view}:`, err);
          set({ loading: false, error: null });
        }
      },

      createEntity: async (name, description, baseClass) => {
        const workspaceId = getCurrentWorkspaceId();
        if (!workspaceId) {
          set({ error: 'No workspace selected' });
          return null;
        }
        
        const timestamp = Date.now();
        const apiName = name.toLowerCase().replace(/[^a-z0-9]/g, '_');
        const newItem: OntologyItem = {
          id: `entity-${timestamp}`,
          workspaceId,
          name,
          type: 'entity',
          description,
          baseClass,
          pluralName: `${name}s`,
          aliases: [],
          status: 'draft',
          visibility: 'normal',
          apiName: `${apiName}_${timestamp.toString(36)}`,
          entityProperties: [],
          actions: [],
          objectCount: 0,
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        set((state) => ({ items: [...state.items, newItem] }));
        return newItem;
      },

      createRelationship: async (name, description, baseProperty) => {
        const workspaceId = getCurrentWorkspaceId();
        if (!workspaceId) {
          set({ error: 'No workspace selected' });
          return null;
        }
        
        const newItem: OntologyItem = {
          id: `rel-${Date.now()}`,
          workspaceId,
          name,
          type: 'relationship',
          description,
          baseClass: baseProperty,
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        set((state) => ({ items: [...state.items, newItem] }));
        return newItem;
      },

      createFolder: async (name) => {
        const workspaceId = getCurrentWorkspaceId();
        if (!workspaceId) {
          set({ error: 'No workspace selected' });
          return null;
        }
        
        const newItem: OntologyItem = {
          id: `folder-${Date.now()}`,
          workspaceId,
          name,
          type: 'folder',
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        set((state) => ({ items: [...state.items, newItem] }));
        return newItem;
      },

      deleteItem: async (id) => {
        set((state) => ({
          items: state.items.filter((item) => item.id !== id),
          selectedItemId: state.selectedItemId === id ? null : state.selectedItemId,
        }));
        return true;
      },

      updateItem: async (id, updates) => {
        set((state) => ({
          items: state.items.map((item) =>
            item.id === id ? { ...item, ...updates, updatedAt: new Date() } : item
          ),
        }));
        return true;
      },

      refreshItems: async () => {
        await get().fetchItems();
      },
      
      getWorkspaceItems: () => {
        const { items } = get();
        const workspaceId = getCurrentWorkspaceId();
        if (!workspaceId) return [];
        return items.filter((item) => item.workspaceId === workspaceId);
      },
      
      // Reference ontology methods
      importReferenceOntology: async (filePath: string) => {
        set({ loadingReference: true, error: null });
        try {
          const baseUrl = getApiUrl();
          const response = await authFetch(`${baseUrl}/api/ontology/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filePath }),
          });
          
          if (response.ok) {
            const data = await response.json();
            set((state) => ({
              referenceOntologies: [...state.referenceOntologies, data],
              expandedReferences: [...state.expandedReferences, data.id],
              loadingReference: false,
            }));
            return data;
          }
          
          // Fallback: read file directly if API fails
          throw new Error('API not available');
        } catch (err) {
          console.error('Failed to import via API, trying direct file read:', err);
          
          // For local development, try to read via files API
          try {
            const baseUrl = getApiUrl();
            const response = await authFetch(`${baseUrl}/api/files/read?path=${encodeURIComponent(filePath)}`);
            
            if (response.ok) {
              const data = await response.json();
              const ontology = get().parseOntologyFile(data.content, 'ttl', filePath);
              set((state) => ({
                referenceOntologies: [...state.referenceOntologies, ontology],
                expandedReferences: [...state.expandedReferences, ontology.id],
                loadingReference: false,
              }));
              return ontology;
            }
          } catch (readErr) {
            console.error('Failed to read file:', readErr);
          }
          
          set({ loadingReference: false, error: 'Failed to import ontology' });
          return null;
        }
      },
      
      removeReferenceOntology: (id: string) => {
        set((state) => ({
          referenceOntologies: state.referenceOntologies.filter((o) => o.id !== id),
          expandedReferences: state.expandedReferences.filter((r) => r !== id),
        }));
      },
      
      parseOntologyFile: (content: string, format: string, filePath: string) => {
        if (format === 'ttl' || filePath.endsWith('.ttl')) {
          return parseTTL(content, filePath);
        }
        // Add more parsers as needed (OWL, RDF, etc.)
        return {
          id: `ref-${Date.now()}`,
          name: filePath.split('/').pop() || 'Unknown',
          filePath,
          format: format as 'ttl' | 'owl' | 'rdf' | 'yaml',
          classes: [],
          properties: [],
          importedAt: new Date(),
        };
      },
    }),
    {
      name: 'nexus-ontology',
      partialize: (state) => ({
        items: state.items,
        expandedFolders: state.expandedFolders,
        referenceOntologies: state.referenceOntologies,
        expandedReferences: state.expandedReferences,
      }),
    }
  )
);

// Selectors
export const selectEntities = (state: OntologyState) =>
  state.items.filter((item) => item.type === 'entity');

export const selectRelationships = (state: OntologyState) =>
  state.items.filter((item) => item.type === 'relationship');

export const selectFolders = (state: OntologyState) =>
  state.items.filter((item) => item.type === 'folder');

export const selectAllReferenceClasses = (state: OntologyState) =>
  state.referenceOntologies.flatMap((o) => o.classes);

export const selectAllReferenceProperties = (state: OntologyState) =>
  state.referenceOntologies.flatMap((o) => o.properties);
