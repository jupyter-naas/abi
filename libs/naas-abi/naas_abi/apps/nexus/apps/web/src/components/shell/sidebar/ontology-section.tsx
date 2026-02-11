'use client';

import React, { useState } from 'react';
import {
  BrainCircuit, ChevronRight, Folder, Box, Link2, Network,
  FolderPlus, RefreshCw, Import, Plus, BookOpen,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useOntologyStore, type OntologyItem } from '@/stores/ontology';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

const OntologyItemComponent = React.memo(function OntologyItemComponent({
  item,
  isActive,
  onClick,
}: {
  item: OntologyItem;
  isActive: boolean;
  onClick: () => void;
}) {
  const isFolder = item.type === 'folder';
  const [expanded, setExpanded] = useState(false);

  const getIcon = () => {
    switch (item.type) {
      case 'entity':
        return <Box size={14} className="flex-shrink-0 text-blue-500" />;
      case 'relationship':
        return <Link2 size={14} className="flex-shrink-0 text-green-500" />;
      case 'folder':
        return <Folder size={14} className="flex-shrink-0 text-muted-foreground" />;
      default:
        return <Network size={14} className="flex-shrink-0 text-muted-foreground" />;
    }
  };

  return (
    <button
      onClick={isFolder ? () => setExpanded(!expanded) : onClick}
      className={cn(
        'group flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-sm transition-colors',
        'hover:bg-workspace-accent-10',
        isActive && 'bg-workspace-accent-15 text-workspace-accent'
      )}
      title={item.description}
    >
      {isFolder && (
        <ChevronRight
          size={12}
          className={cn('flex-shrink-0 transition-transform', expanded && 'rotate-90')}
        />
      )}
      {!isFolder && <span className="w-3" />}
      {getIcon()}
      <span className="flex-1 truncate">{item.name}</span>
    </button>
  );
});

export function OntologySection({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const { currentWorkspaceId } = useWorkspaceStore();
  const {
    items: ontologyItems,
    loading: ontologyLoading,
    selectedItemId,
    setSelectedItem,
    createFolder: createOntologyFolder,
    refreshItems: refreshOntology,
    referenceOntologies,
    expandedReferences,
    toggleReference,
  } = useOntologyStore();

  const entities = ontologyItems.filter((item) => item.type === 'entity');
  const relationships = ontologyItems.filter((item) => item.type === 'relationship');

  return (
    <CollapsibleSection
      id="ontology"
      icon={<BrainCircuit size={18} />}
      label="Ontology"
      description="Define entities, relationships, and schemas"
      href={getWorkspacePath(currentWorkspaceId, '/ontology')}
      collapsed={collapsed}
    >
      {/* Toolbar */}
      <div className="flex items-center gap-0.5 px-1 pb-1">
        <button
          onClick={() => router.push(getWorkspacePath(currentWorkspaceId, '/ontology?view=create-entity'))}
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="New Entity"
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

      {/* Entities */}
      {entities.length > 0 && (
        <div className="space-y-0.5">
          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Entities ({entities.length})
          </p>
          {entities.map((item) => (
            <OntologyItemComponent
              key={item.id}
              item={item}
              isActive={selectedItemId === item.id}
              onClick={() => {
                setSelectedItem(item.id);
                router.push(getWorkspacePath(currentWorkspaceId, '/ontology'));
              }}
            />
          ))}
        </div>
      )}

      {/* Relationships */}
      {relationships.length > 0 && (
        <div className="space-y-0.5">
          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Relationships ({relationships.length})
          </p>
          {relationships.map((item) => (
            <OntologyItemComponent
              key={item.id}
              item={item}
              isActive={selectedItemId === item.id}
              onClick={() => {
                setSelectedItem(item.id);
                router.push(getWorkspacePath(currentWorkspaceId, '/ontology'));
              }}
            />
          ))}
        </div>
      )}

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
      {ontologyItems.length === 0 && referenceOntologies.length === 0 && (
        <p className="px-2 py-2 text-xs text-muted-foreground">
          {ontologyLoading ? 'Loading...' : 'No items yet'}
        </p>
      )}
    </CollapsibleSection>
  );
}
