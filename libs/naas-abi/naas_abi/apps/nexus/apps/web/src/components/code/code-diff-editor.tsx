'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { ensureMonacoConfigured } from '@/lib/monaco';

const DiffEditor = dynamic(
  () =>
    ensureMonacoConfigured().then(() =>
      import('@monaco-editor/react').then((m) => m.DiffEditor),
    ),
  { ssr: false },
);

interface CodeDiffEditorProps {
  path: string;
  original: string;
  modified: string;
  language: string;
}

/** Monaco diff view with deferred mount to avoid model-disposal races. */
export function CodeDiffEditor({ path, original, modified, language }: CodeDiffEditorProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(false);
    let cancelled = false;
    let frame = 0;

    void ensureMonacoConfigured().then(() => {
      frame = requestAnimationFrame(() => {
        if (!cancelled) setMounted(true);
      });
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      setMounted(false);
    };
  }, [path]);

  if (!mounted) {
    return (
      <div className="flex h-full items-center justify-center bg-[#1e1e1e]">
        <span className="text-xs text-zinc-500">Loading diff...</span>
      </div>
    );
  }

  return (
    <DiffEditor
      key={path}
      height="100%"
      language={language}
      original={original}
      modified={modified}
      theme="vs-dark"
      keepCurrentOriginalModel
      keepCurrentModifiedModel
      options={{
        fontSize: 13,
        fontFamily: 'JetBrains Mono, Menlo, Monaco, Consolas, monospace',
        readOnly: true,
        renderSideBySide: true,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        minimap: { enabled: false },
        renderOverviewRuler: true,
      }}
      loading={
        <div className="flex h-full items-center justify-center bg-[#1e1e1e]">
          <span className="text-xs text-zinc-500">Loading diff...</span>
        </div>
      }
    />
  );
}
