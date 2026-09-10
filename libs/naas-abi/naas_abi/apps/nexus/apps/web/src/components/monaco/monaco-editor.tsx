'use client';

import dynamic from 'next/dynamic';
import type { EditorProps } from '@monaco-editor/react';
import { useWorkspaceStore } from '@/stores/workspace';

/**
 * Shared Monaco mount used by Slides View → Code and Events View → JSON.
 * Loads `@monaco-editor/react` on the client only.
 */
const Monaco = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
      Loading editor…
    </div>
  ),
});

export const MONACO_EDITOR_DEFAULTS = {
  theme: 'vs-dark' as const,
  height: '100%',
  options: {
    minimap: { enabled: false },
    fontSize: 13,
    wordWrap: 'on' as const,
    automaticLayout: true,
  },
};

export function MonacoEditor({
  theme = MONACO_EDITOR_DEFAULTS.theme,
  height = MONACO_EDITOR_DEFAULTS.height,
  options,
  onMount,
  ...props
}: EditorProps) {
  return (
    <Monaco
      {...props}
      theme={theme}
      height={height}
      options={{ ...MONACO_EDITOR_DEFAULTS.options, ...options }}
      onMount={(editor, monaco) => {
        // Monaco defaults ⌘K to a chord starter; route it to the Abi pane.
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK, () => {
          useWorkspaceStore.getState().toggleContextPanel();
        });
        onMount?.(editor, monaco);
      }}
    />
  );
}
