'use client';

import { useState } from 'react';
import {
  Box,
  Calendar,
  Check,
  ChevronRight,
  Hash,
  HelpCircle,
  LayoutGrid,
  Link2,
  List,
  Mail,
  Pencil,
  Plus,
  Star,
  ToggleLeft,
  Type,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type {
  EntityProperty,
  EntityStatus,
  EntityVisibility,
  OntologyItem,
  ReferenceClass,
} from '@/stores/ontology';

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

export interface EntityDetailViewProps {
  item: OntologyItem;
  allClasses: Array<ReferenceClass & { ontologyName: string }>;
  onUpdate: (updates: Partial<OntologyItem>) => void;
}

export function EntityDetailView({ item, allClasses, onUpdate }: EntityDetailViewProps) {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [newAlias, setNewAlias] = useState('');
  const [showAddProperty, setShowAddProperty] = useState(false);
  const [newPropertyName, setNewPropertyName] = useState('');
  const [newPropertyType, setNewPropertyType] = useState<string>('string');

  const baseClass = allClasses.find((c) => c.iri === item.baseClass);
  const propertyCount = item.entityProperties?.length || 0;
  const additionalSectionTables = ENTITY_CENTER_SECTIONS.filter(
    (section) => !['Overview', 'Properties', 'Action types'].includes(section),
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
      <div className="flex flex-1 flex-col overflow-hidden">
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
                {item.type === 'entity' ? 'Class' : 'Object Properties'} • {item.objectCount || 0} objects
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

        <div className="flex-1 overflow-y-auto p-6">
          <div className="flex gap-6">
            <div className="flex-1 space-y-1">
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

              <div className="rounded-lg border divide-y">
                <div className="flex items-center px-4 py-3">
                  <span className="w-40 text-sm text-muted-foreground">URIRef</span>
                  <span className="font-mono text-sm text-muted-foreground truncate">{item.id}</span>
                </div>

                <div className="flex items-center px-4 py-3">
                  <span className="w-40 text-sm text-muted-foreground">
                    {item.type === 'relationship' ? 'Subproperty of' : 'Subclass of'}
                  </span>
                  <span className="text-sm">{item.parentName || 'None'}</span>
                </div>

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

                <div className="flex items-center px-4 py-3">
                  <span className="w-40 text-sm text-muted-foreground">Example</span>
                  <span className="text-sm">{baseClass?.examples || 'No example'}</span>
                </div>

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

                <div className="flex items-center px-4 py-3">
                  <span className="w-40 text-sm text-muted-foreground">Contributors</span>
                  <span className="text-sm">{item.contributors?.join(', ') || 'None'}</span>
                </div>
              </div>

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

            <div className="w-64 flex-shrink-0 space-y-4">
              <div className="rounded-lg border p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Status</span>
                  <select
                    value={item.status || 'draft'}
                    onChange={(e) => onUpdate({ status: e.target.value as EntityStatus })}
                    className={cn(
                      'rounded px-2 py-0.5 text-sm font-medium',
                      STATUS_COLORS[item.status || 'draft'],
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
