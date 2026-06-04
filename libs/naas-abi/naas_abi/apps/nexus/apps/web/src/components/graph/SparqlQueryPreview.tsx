'use client';

import { useMemo, useState } from 'react';
import { Check, ChevronDown, ChevronRight, ChevronUp, Code, Copy, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { buildFullQuery, type SparqlStep } from '@/lib/sparql-steps';

interface SparqlQueryPreviewProps {
  steps: SparqlStep[];
  graphUri: string;
  collapsed: boolean;
  onToggle: () => void;
  onRemoveStep: (id: string) => void;
}

export function SparqlQueryPreview({
  steps,
  graphUri,
  collapsed,
  onToggle,
  onRemoveStep,
}: SparqlQueryPreviewProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [fullQueryExpanded, setFullQueryExpanded] = useState(false);

  const allExpanded = steps.length > 0 && steps.every((s) => expandedIds.has(s.id));

  function expandAll() {
    setExpandedIds(new Set(steps.map((s) => s.id)));
  }

  function collapseAll() {
    setExpandedIds(new Set());
  }

  const fullQuery = useMemo(
    () => buildFullQuery(steps, graphUri),
    [steps, graphUri]
  );

  function copyText(text: string, id: string) {
    void navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  return (
    <section className="flex flex-col border-t">
      <header className="flex items-center justify-between border-b bg-muted/40 px-4 py-2">
        <button
          type="button"
          onClick={onToggle}
          className="flex items-center gap-2 text-left hover:text-workspace-accent"
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          {collapsed ? (
            <ChevronRight size={14} className="text-muted-foreground" />
          ) : (
            <ChevronDown size={14} className="text-muted-foreground" />
          )}
          <Code size={14} className="text-muted-foreground" />
          <h3 className="text-sm font-semibold">SPARQL Query Preview</h3>
          {steps.length > 0 && (
            <span className="rounded-full bg-workspace-accent/10 px-1.5 py-0.5 text-xs font-medium text-workspace-accent">
              {steps.length}
            </span>
          )}
        </button>
        {!collapsed && steps.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={allExpanded ? collapseAll : expandAll}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              title={allExpanded ? 'Collapse all steps' : 'Expand all steps'}
            >
              {allExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {allExpanded ? 'Collapse all' : 'Expand all'}
            </button>
            <span className="text-muted-foreground/40">|</span>
            <button
              type="button"
              onClick={() => copyText(fullQuery, '__full__')}
              className="flex items-center gap-1.5 rounded border px-2 py-1 text-xs hover:bg-muted"
              title="Copy full CONSTRUCT query to clipboard"
            >
              {copiedId === '__full__' ? (
                <Check size={12} className="text-green-500" />
              ) : (
                <Copy size={12} />
              )}
              Copy full query
            </button>
          </div>
        )}
      </header>

      {!collapsed && (
        <div className="max-h-[60vh] overflow-auto p-2 space-y-1">
          {steps.length === 0 ? (
            <p className="px-2 py-6 text-center text-xs text-muted-foreground">
              No steps recorded yet. Use Search, Class filter, or select instances to start building
              a query pipeline.
            </p>
          ) : (
            <>
              {steps.map((step, idx) => (
                <StepRow
                  key={step.id}
                  step={step}
                  number={idx + 1}
                  isExpanded={expandedIds.has(step.id)}
                  onToggle={() =>
                    setExpandedIds((prev) => {
                      const next = new Set(prev);
                      if (next.has(step.id)) next.delete(step.id);
                      else next.add(step.id);
                      return next;
                    })
                  }
                  copied={copiedId === step.id}
                  onCopy={() => copyText(step.sparql, step.id)}
                  onRemove={() => onRemoveStep(step.id)}
                />
              ))}

              <div className="mt-2 rounded border">
                <button
                  type="button"
                  onClick={() => setFullQueryExpanded((p) => !p)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium hover:bg-muted/50"
                >
                  {fullQueryExpanded ? (
                    <ChevronUp size={12} className="text-muted-foreground" />
                  ) : (
                    <ChevronDown size={12} className="text-muted-foreground" />
                  )}
                  <Code size={12} className="text-muted-foreground" />
                  <span>Full CONSTRUCT query</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {steps.length} step{steps.length !== 1 ? 's' : ''}
                  </span>
                </button>
                {fullQueryExpanded && (
                  <div className="border-t">
                    <div className="flex justify-end px-3 py-1">
                      <button
                        type="button"
                        onClick={() => copyText(fullQuery, '__full2__')}
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                      >
                        {copiedId === '__full2__' ? (
                          <><Check size={11} className="text-green-500" /> Copied</>
                        ) : (
                          <><Copy size={11} /> Copy</>
                        )}
                      </button>
                    </div>
                    <pre className="overflow-x-auto px-3 pb-3 text-xs font-mono leading-relaxed text-foreground whitespace-pre">
                      {fullQuery}
                    </pre>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}

// ── Step row ──────────────────────────────────────────────────────────────────

const STEP_META: Record<SparqlStep['type'], { label: string; color: string; bg: string }> = {
  search:              { label: 'Search',              color: 'text-blue-600 dark:text-blue-400',    bg: 'bg-blue-50 dark:bg-blue-950/40' },
  class_filter:        { label: 'Class filter',        color: 'text-violet-600 dark:text-violet-400', bg: 'bg-violet-50 dark:bg-violet-950/40' },
  property_filter:     { label: 'Property filter',     color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-950/40' },
  instance_select:     { label: 'Instance select',     color: 'text-green-600 dark:text-green-400',   bg: 'bg-green-50 dark:bg-green-950/40' },
  relation_select:     { label: 'Relation select',     color: 'text-orange-600 dark:text-orange-400', bg: 'bg-orange-50 dark:bg-orange-950/40' },
  exclusion:           { label: 'Exclusion',           color: 'text-red-600 dark:text-red-400',       bg: 'bg-red-50 dark:bg-red-950/40' },
  default_properties:  { label: 'Default properties',  color: 'text-teal-600 dark:text-teal-400',     bg: 'bg-teal-50 dark:bg-teal-950/40' },
  property_projection: { label: 'Property projection', color: 'text-cyan-600 dark:text-cyan-400',     bg: 'bg-cyan-50 dark:bg-cyan-950/40' },
};

interface StepRowProps {
  step: SparqlStep;
  number: number;
  isExpanded: boolean;
  onToggle: () => void;
  copied: boolean;
  onCopy: () => void;
  onRemove: () => void;
}

function StepRow({ step, number, isExpanded, onToggle, copied, onCopy, onRemove }: StepRowProps) {
  const meta = STEP_META[step.type];

  return (
    <div className="group rounded border bg-card">
      <div className="flex items-center">
        <button
          type="button"
          onClick={onToggle}
          className="flex flex-1 items-center gap-2 px-3 py-2 text-left hover:bg-muted/50 min-w-0"
        >
          <span className="w-5 shrink-0 text-right text-xs font-mono text-muted-foreground">
            {number}
          </span>
          <span
            className={cn(
              'shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
              meta.color,
              meta.bg
            )}
          >
            {meta.label}
          </span>
          <span className="flex-1 truncate text-xs">{step.label}</span>
        {isExpanded ? (
          <ChevronUp size={12} className="shrink-0 text-muted-foreground" />
        ) : (
          <ChevronDown size={12} className="shrink-0 text-muted-foreground" />
        )}
        </button>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          className="mr-2 shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-950/40"
          title="Remove step"
        >
          <Trash2 size={12} />
        </button>
      </div>

      {isExpanded && (
        <div className="border-t bg-muted/20">
          <div className="flex items-center justify-end px-3 py-1">
            <button
              type="button"
              onClick={onCopy}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              {copied ? (
                <><Check size={11} className="text-green-500" /> Copied</>
              ) : (
                <><Copy size={11} /> Copy</>
              )}
            </button>
          </div>
          <pre className="overflow-x-auto px-3 pb-3 text-xs font-mono leading-relaxed text-foreground whitespace-pre">
            {step.sparql}
          </pre>
        </div>
      )}
    </div>
  );
}
