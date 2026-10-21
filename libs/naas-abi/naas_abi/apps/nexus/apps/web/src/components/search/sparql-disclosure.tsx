'use client';

import { useState } from 'react';
import { Check, Code2, Copy } from 'lucide-react';
import { cn } from '@/lib/utils';

/** "Show SPARQL": every block on the search page can show the query that filled it. */
export function SparqlDisclosure({ sparql, label = 'SPARQL Query', className }: { sparql: string; label?: string; className?: string }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  if (!sparql) return null;
  return (
    <div className={cn('text-xs', className)}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <Code2 size={12} /> {open ? `Hide ${label}` : label}
      </button>
      {open && (
        <div className="relative mt-1">
          <button
            type="button"
            onClick={() => { void navigator.clipboard?.writeText(sparql.trim()); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
            className="absolute right-2 top-2 rounded p-1 text-muted-foreground hover:bg-background hover:text-foreground"
            aria-label="Copy SPARQL"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
          </button>
          <pre className="max-h-80 overflow-auto rounded-md border bg-muted/50 p-3 pr-8 font-mono text-[11px] leading-relaxed">{sparql.trim()}</pre>
        </div>
      )}
    </div>
  );
}
