'use client';

/** Monaco, themed like the workspace, for raw values and the editor. */
import { useEffect, useState } from 'react';
import type { Monaco } from '@monaco-editor/react';
import { MonacoEditor } from '@/components/monaco/monaco-editor';

let turtleRegistered = false;

/** Turtle / N-Triples highlighting (Monaco has none built in). */
export function registerTurtle(monaco: Monaco): void {
  if (turtleRegistered) return;
  turtleRegistered = true;
  monaco.languages.register({ id: 'turtle', extensions: ['.ttl', '.nt'], aliases: ['Turtle'] });
  monaco.languages.setMonarchTokensProvider('turtle', {
    tokenizer: {
      root: [
        [/#.*$/, 'comment'],
        [/@(prefix|base)\b/, 'keyword'],
        [/\b(PREFIX|BASE|a|true|false)\b/, 'keyword'],
        [/<[^>\s]*>/, 'type.identifier'],
        [/"""/, { token: 'string', next: '@longString' }],
        [/"([^"\\]|\\.)*"/, 'string'],
        [/'([^'\\]|\\.)*'/, 'string'],
        [/@[a-zA-Z]+(-[a-zA-Z0-9]+)*/, 'annotation'],
        [/\^\^/, 'operator'],
        [/_:[\w.-]+/, 'variable.predefined'],
        [/[a-zA-Z_][\w.-]*:[\w.-]*|:[\w.-]+/, 'variable'],
        [/-?\d+(\.\d+)?([eE][+-]?\d+)?/, 'number'],
        [/[;,.\[\]()]/, 'delimiter'],
      ],
      longString: [
        [/"""/, { token: 'string', next: '@pop' }],
        [/./, 'string'],
      ],
    },
  });
}

function useDarkTheme(): boolean {
  const [dark, setDark] = useState(true);
  useEffect(() => {
    const root = document.documentElement;
    const read = () => setDark(root.classList.contains('dark'));
    read();
    const observer = new MutationObserver(read);
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  return dark;
}

export function CodeView({
  value,
  language,
  onChange,
  readOnly = true,
  height = '100%',
}: {
  value: string;
  language: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  height?: string;
}) {
  const dark = useDarkTheme();
  return (
    <div className="data-code" style={{ height }}>
      <MonacoEditor
        value={value}
        language={language}
        theme={dark ? 'vs-dark' : 'vs'}
        beforeMount={registerTurtle}
        onChange={(next) => onChange?.(next ?? '')}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 12,
          lineNumbersMinChars: 3,
          scrollBeyondLastLine: false,
          wordWrap: 'on',
          renderLineHighlight: readOnly ? 'none' : 'line',
          padding: { top: 10, bottom: 10 },
          automaticLayout: true,
          tabSize: 2,
        }}
      />
    </div>
  );
}
