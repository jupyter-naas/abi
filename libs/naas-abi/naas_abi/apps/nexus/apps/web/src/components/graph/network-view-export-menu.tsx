'use client';

import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Download, Loader2 } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { serializeTriples, type TripleExportFormat } from '@/lib/triples-export';
import { cn } from '@/lib/utils';

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

const TRIPLE_EXPORT_FORMATS: { id: TripleExportFormat; label: string }[] = [
  { id: 'nt', label: 'N-Triples (.nt)' },
  { id: 'ttl', label: 'Turtle (.ttl)' },
  { id: 'owl', label: 'OWL (.owl)' },
];

export function NetworkViewExportMenu({
  workspaceId,
  triples,
  onExportExcel,
  disabled,
}: {
  workspaceId: string;
  triples: Array<{ s: string; p: string; o: string; isLiteral: boolean }>;
  onExportExcel: () => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const handleTripleExport = async (format: TripleExportFormat) => {
    if (triples.length === 0) return;
    setExporting(true);
    try {
      const res = await authFetch(`${getApiUrl()}/api/graph/discovery/triples-export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          triples: triples.map((t) => ({
            s: t.s,
            p: t.p,
            o: t.o,
            is_literal: t.isLiteral,
          })),
          format,
        }),
      });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const data = (await res.json()) as {
        content: string;
        filename: string;
        media_type: string;
      };
      downloadBlob(data.content, data.filename, data.media_type);
    } catch {
      const { content, filename, mime } = serializeTriples(triples, format);
      downloadBlob(content, filename, mime);
    } finally {
      setExporting(false);
      setOpen(false);
    }
  };

  return (
    <div ref={ref} className="relative flex items-center">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        disabled={disabled || exporting}
        className={cn(
          'flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground',
          (disabled || exporting) && 'cursor-not-allowed opacity-50'
        )}
        title="Export selected data"
      >
        {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
        {exporting ? 'Exporting...' : 'Export'}
      </button>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        disabled={disabled || exporting}
        className={cn(
          'ml-0.5 flex items-center rounded px-1 py-0.5 text-muted-foreground hover:text-foreground',
          (disabled || exporting) && 'cursor-not-allowed opacity-50'
        )}
        title="Select export format"
      >
        <ChevronDown size={12} />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 min-w-[180px] rounded-md border bg-background py-1 shadow-md">
          <p className="px-3 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Triples
          </p>
          {TRIPLE_EXPORT_FORMATS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => void handleTripleExport(id)}
              disabled={triples.length === 0}
              className="flex w-full items-center px-3 py-1.5 text-left text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              {label}
            </button>
          ))}
          <div className="my-1 h-px bg-border" />
          <button
            type="button"
            onClick={() => {
              onExportExcel();
              setOpen(false);
            }}
            className="flex w-full items-center px-3 py-1.5 text-left text-sm hover:bg-muted"
          >
            Excel (.csv)
          </button>
        </div>
      )}
    </div>
  );
}
