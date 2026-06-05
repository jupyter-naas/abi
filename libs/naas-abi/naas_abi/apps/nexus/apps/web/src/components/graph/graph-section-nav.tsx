'use client';

import type { ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { Network, Search, Users } from 'lucide-react';
import { cn } from '@/lib/utils';

export type GraphSection = 'network' | 'explore' | 'individuals';

const SECTIONS: Array<{
  id: GraphSection;
  label: string;
  icon: typeof Network;
  path: string;
}> = [
  { id: 'network', label: 'Network', icon: Network, path: 'network' },
  { id: 'explore', label: 'Explore', icon: Search, path: 'explore' },
  { id: 'individuals', label: 'Individuals', icon: Users, path: 'individuals' },
];

export function GraphSectionNav({
  workspaceId,
  active,
  trailing,
  onNavigate,
}: {
  workspaceId: string;
  active: GraphSection;
  trailing?: ReactNode;
  onNavigate?: (section: GraphSection) => void;
}) {
  const router = useRouter();

  const handleNavigate = (section: GraphSection, path: string) => {
    if (onNavigate) {
      onNavigate(section);
      return;
    }
    router.push(`/workspace/${workspaceId}/graph/${path}`);
  };

  return (
    <div className="flex h-10 items-center justify-between border-b bg-muted/30 px-4">
      <div className="flex items-center gap-1">
        {SECTIONS.map(({ id, label, icon: Icon, path }) => (
          <button
            key={id}
            type="button"
            onClick={() => handleNavigate(id, path)}
            className={cn(
              'flex items-center gap-2 rounded-md px-3 py-1 text-sm',
              active === id ? 'bg-background' : 'text-muted-foreground hover:bg-background'
            )}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>
      {trailing ? <div className="flex items-center gap-3">{trailing}</div> : null}
    </div>
  );
}
