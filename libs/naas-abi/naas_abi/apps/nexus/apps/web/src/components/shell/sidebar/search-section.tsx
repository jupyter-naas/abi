'use client';

import React from 'react';
import { ChevronRight, Eye, EyeOff, Globe, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSearchStore, type SearchSource, type SourceCategory } from '@/stores/search';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath, searchIconMap } from './utils';

const SearchSourceItem = React.memo(function SearchSourceItem({
  source,
  onToggle,
}: {
  source: SearchSource;
  onToggle: () => void;
}) {
  const IconComponent = searchIconMap[source.icon] || Globe;

  return (
    <button
      onClick={onToggle}
      className={cn(
        'group flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-sm transition-colors',
        'hover:bg-workspace-accent-10',
        source.enabled ? 'text-foreground' : 'text-muted-foreground'
      )}
      title={source.description}
    >
      <IconComponent size={14} className="flex-shrink-0" />
      <span className="flex-1 truncate">{source.name}</span>
      {source.enabled ? (
        <Eye size={12} className="flex-shrink-0 text-workspace-accent opacity-0 group-hover:opacity-100" />
      ) : (
        <EyeOff size={12} className="flex-shrink-0 opacity-0 group-hover:opacity-100" />
      )}
    </button>
  );
});

const SearchCategoryGroup = React.memo(function SearchCategoryGroup({
  category,
  label,
  sources,
  isExpanded,
  onToggle,
  onToggleSource,
}: {
  category: SourceCategory;
  label: string;
  sources: SearchSource[];
  isExpanded: boolean;
  onToggle: () => void;
  onToggleSource: (id: string) => void;
}) {
  const enabledCount = sources.filter((s) => s.enabled).length;

  return (
    <div className="space-y-0.5">
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-1 rounded-md px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        <ChevronRight
          size={12}
          className={cn('transition-transform', isExpanded && 'rotate-90')}
        />
        <span className="flex-1 truncate text-left">{label}</span>
        <span className="text-[10px]">
          {enabledCount}/{sources.length}
        </span>
      </button>
      {isExpanded && (
        <div className="ml-3 space-y-0.5">
          {sources.map((source) => (
            <SearchSourceItem
              key={source.id}
              source={source}
              onToggle={() => onToggleSource(source.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
});

export function SearchSection({ collapsed }: { collapsed: boolean }) {
  const { currentWorkspaceId } = useWorkspaceStore();
  const {
    sources,
    expandedCategories,
    toggleSource,
    toggleCategory,
  } = useSearchStore();

  const publicSources = sources.filter((s) => s.category === 'public');
  const privateSources = sources.filter((s) => s.category === 'private');
  const customSources = sources.filter((s) => s.category === 'custom');

  return (
    <CollapsibleSection
      id="search"
      icon={<Search size={18} />}
      label="Search"
      description="Semantic search across all your knowledge"
      href={getWorkspacePath(currentWorkspaceId, '/search')}
      collapsed={collapsed}
    >
      <SearchCategoryGroup
        category="public"
        label="Public"
        sources={publicSources}
        isExpanded={expandedCategories.includes('public')}
        onToggle={() => toggleCategory('public')}
        onToggleSource={toggleSource}
      />
      <SearchCategoryGroup
        category="private"
        label="Private"
        sources={privateSources}
        isExpanded={expandedCategories.includes('private')}
        onToggle={() => toggleCategory('private')}
        onToggleSource={toggleSource}
      />
      <SearchCategoryGroup
        category="custom"
        label="Custom"
        sources={customSources}
        isExpanded={expandedCategories.includes('custom')}
        onToggle={() => toggleCategory('custom')}
        onToggleSource={toggleSource}
      />
    </CollapsibleSection>
  );
}
