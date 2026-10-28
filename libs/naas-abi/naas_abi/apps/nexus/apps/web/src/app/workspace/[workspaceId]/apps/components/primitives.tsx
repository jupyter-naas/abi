'use client';

import { useState } from 'react';
import { Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PropertyTags } from '@/components/database-view/primitives';
import { PROPERTY_BY_KEY, propertyValues, type AppRecord, type PropertyKey } from './types';

// ---------------------------------------------------------------------------
// App icon
// ---------------------------------------------------------------------------

const ICON_DIMS = {
  sm: 'h-6 w-6 text-sm',
  md: 'h-9 w-9 text-lg',
  lg: 'h-12 w-12 text-2xl',
} as const;

const ICON_GLYPH = { sm: 13, md: 18, lg: 24 } as const;

export function AppIcon({
  record,
  size = 'md',
}: {
  record: Pick<AppRecord, 'avatarUrl' | 'iconEmoji' | 'name'>;
  size?: keyof typeof ICON_DIMS;
}) {
  const [failed, setFailed] = useState(false);

  if (record.avatarUrl && !failed) {
    return (
      <span
        className={cn(
          ICON_DIMS[size],
          'relative flex-shrink-0 overflow-hidden p-0',
        )}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={record.avatarUrl}
          alt={record.name}
          className="absolute inset-0 h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      </span>
    );
  }
  return (
    <div
      className={cn(
        ICON_DIMS[size],
        'flex flex-shrink-0 items-center justify-center rounded-lg bg-workspace-accent/10 leading-none',
      )}
    >
      {record.iconEmoji ?? <Bot size={ICON_GLYPH[size]} className="text-workspace-accent" />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Property rendering
// ---------------------------------------------------------------------------

const CATEGORY_COLORS: Record<string, string> = {
  application: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  alpha: 'bg-amber-500/10 text-amber-600',
  ai: 'bg-blue-500/10 text-blue-500',
  domain: 'bg-amber-500/10 text-amber-600',
  core: 'bg-workspace-accent/10 text-workspace-accent',
  external: 'bg-muted text-muted-foreground',
};

function tagClass(key: PropertyKey, value: string): string {
  if (key === 'category') return CATEGORY_COLORS[value] ?? 'bg-muted text-muted-foreground';
  return 'bg-muted text-muted-foreground';
}

/** A property value as Notion renders it: tags for selects, plain text otherwise. */
export function PropertyValue({
  record,
  propertyKey,
  className,
}: {
  record: AppRecord;
  propertyKey: PropertyKey;
  className?: string;
}) {
  return (
    <PropertyTags
      values={propertyValues(record, propertyKey)}
      type={PROPERTY_BY_KEY[propertyKey].type}
      tagClass={(value) => tagClass(propertyKey, value)}
      className={className}
    />
  );
}

// Toolbar menus are shared by every database surface.
export { MenuSelect, Popover, ToolbarButton } from '@/components/database-view/primitives';
