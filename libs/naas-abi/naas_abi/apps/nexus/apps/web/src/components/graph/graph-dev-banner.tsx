'use client';

import { AlertTriangle } from 'lucide-react';

/**
 * Shared "under active development" notice for the Knowledge Graph.
 *
 * Originally lived only on the legacy Explore page; it now renders at the top of every
 * KG section (Network, Individuals, Composer, Import, Export) so the caveat is visible
 * wherever the user lands. Place it directly under <GraphSectionNav>.
 */
export function GraphDevBanner() {
  return (
    <div className="flex items-start gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
      <p>
        <span className="font-medium">The Knowledge Graph is under active development.</span>{' '}
        Features may change, data previews can be incomplete, and you may encounter bugs or
        unexpected behavior. Report issues to your workspace admin.
      </p>
    </div>
  );
}
