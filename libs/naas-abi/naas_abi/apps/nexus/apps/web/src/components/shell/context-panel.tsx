'use client';

import { useState, useEffect } from 'react';
import { X, FileText, Network, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';

export function ContextPanel() {
  const [mounted, setMounted] = useState(false);
  const { contextPanelOpen, toggleContextPanel } = useWorkspaceStore();

  useEffect(() => {
    setMounted(true);
  }, []);

  // On server render as closed to prevent hydration mismatch
  if (!mounted || !contextPanelOpen) return null;

  return (
    <aside className="glass flex h-full w-80 flex-col border-l border-border/50">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b px-4">
        <h2 className="font-semibold">Context</h2>
        <button
          onClick={toggleContextPanel}
          className={cn(
            'flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors',
            'hover:bg-accent hover:text-accent-foreground'
          )}
        >
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {/* Active context */}
        <div className="mb-6">
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">Active Context</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-3 rounded-lg border p-3 text-sm">
              <FileText size={16} className="text-muted-foreground" />
              <span>No files attached</span>
            </div>
          </div>
        </div>

        {/* Related entities */}
        <div className="mb-6">
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">Related Entities</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-3 rounded-lg border p-3 text-sm">
              <Network size={16} className="text-muted-foreground" />
              <span>No entities linked</span>
            </div>
          </div>
        </div>

        {/* Recent activity */}
        <div>
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">Recent Activity</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-3 rounded-lg border p-3 text-sm">
              <Clock size={16} className="text-muted-foreground" />
              <span>No recent activity</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
