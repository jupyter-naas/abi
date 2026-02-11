'use client';

import { useEffect, useCallback } from 'react';
import { Header } from '@/components/shell/header';
import { FileCode, Plus, Terminal, X, Save } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFilesStore } from '@/stores/files';
import { usePrompt } from '@/components/ui/dialogs';
import Editor from '@monaco-editor/react';

// Get Monaco language ID from file extension
function getLanguage(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();
  const languageMap: Record<string, string> = {
    py: 'python',
    js: 'javascript',
    ts: 'typescript',
    tsx: 'typescript',
    jsx: 'javascript',
    json: 'json',
    md: 'markdown',
    yaml: 'yaml',
    yml: 'yaml',
    html: 'html',
    css: 'css',
    scss: 'scss',
    less: 'less',
    sql: 'sql',
    sh: 'shell',
    bash: 'shell',
    zsh: 'shell',
    c: 'c',
    cpp: 'cpp',
    h: 'c',
    hpp: 'cpp',
    java: 'java',
    go: 'go',
    rs: 'rust',
    rb: 'ruby',
    php: 'php',
    swift: 'swift',
    kt: 'kotlin',
    scala: 'scala',
    r: 'r',
    xml: 'xml',
    graphql: 'graphql',
    dockerfile: 'dockerfile',
    toml: 'toml',
    ini: 'ini',
    env: 'plaintext',
  };
  return languageMap[ext || ''] || 'plaintext';
}

export default function LabPage() {
  const {
    openFiles,
    activeFile,
    fileContents,
    unsavedChanges,
    setActiveFile,
    closeFile,
    setFileContent,
    saveFile,
    createFile,
    openFile,
  } = useFilesStore();
  const { prompt, dialog: promptDialog } = usePrompt();

  // Keyboard shortcut for save (Cmd/Ctrl + S)
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      if (activeFile) {
        saveFile(activeFile);
      }
    }
  }, [activeFile, saveFile]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const handleNewFile = async () => {
    const name = await prompt({
      title: 'New File',
      description: 'Enter a name for the new file',
      defaultValue: 'untitled.py',
      confirmLabel: 'Create',
    });
    if (name) {
      const result = await createFile(name);
      if (result) {
        openFile(result.path);
      }
    }
  };

  const activeContent = activeFile ? fileContents[activeFile] : undefined;
  const hasUnsavedChanges = activeFile ? unsavedChanges[activeFile] : false;
  const language = activeFile ? getLanguage(activeFile) : 'plaintext';

  return (
    <>
    {promptDialog}
    <div className="flex h-full flex-col">
      <Header title="Lab" subtitle="Embedded development environment" />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Tabs */}
        <div className="flex h-10 items-center gap-1 border-b bg-muted/30 px-2">
          {openFiles.map((path) => {
            const filename = path.split('/').pop() || path;
            const isActive = path === activeFile;
            const isUnsaved = unsavedChanges[path];
            
            return (
              <div
                key={path}
                onClick={() => setActiveFile(path)}
                className={cn(
                  'group flex items-center gap-2 rounded-md px-3 py-1 text-sm cursor-pointer transition-colors',
                  isActive ? 'bg-background' : 'hover:bg-background/50'
                )}
              >
                <FileCode size={14} />
                <span className={cn(isUnsaved && 'italic')}>
                  {filename}
                  {isUnsaved && ' •'}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    closeFile(path);
                  }}
                  className="rounded p-0.5 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100"
                >
                  <X size={12} />
                </button>
              </div>
            );
          })}
        </div>

        {/* Editor area */}
        <div className="flex flex-1 overflow-hidden">
          {activeFile && activeContent !== undefined ? (
            <div className="flex flex-1 flex-col">
              {/* Editor toolbar */}
              <div className="flex h-8 items-center justify-between border-b bg-muted/20 px-3">
                <span className="text-xs text-muted-foreground">
                  {activeFile} — {language}
                </span>
                <div className="flex items-center gap-2">
                  {hasUnsavedChanges && (
                    <button
                      onClick={() => saveFile(activeFile)}
                      className="flex items-center gap-1 rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <Save size={12} />
                      Save
                    </button>
                  )}
                </div>
              </div>
              
              {/* Monaco Editor */}
              <div className="flex-1">
                <Editor
                  height="100%"
                  language={language}
                  value={activeContent}
                  onChange={(value) => setFileContent(activeFile, value || '')}
                  theme="vs-dark"
                  options={{
                    fontSize: 14,
                    fontFamily: 'JetBrains Mono, Menlo, Monaco, Consolas, monospace',
                    minimap: { enabled: true },
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    tabSize: 2,
                    wordWrap: 'on',
                    lineNumbers: 'on',
                    renderWhitespace: 'selection',
                    bracketPairColorization: { enabled: true },
                    padding: { top: 16 },
                  }}
                  loading={
                    <div className="flex h-full items-center justify-center bg-zinc-900">
                      <span className="text-sm text-muted-foreground">Loading editor...</span>
                    </div>
                  }
                />
              </div>
            </div>
          ) : (
            /* Empty state */
            <div className="flex flex-1 items-center justify-center bg-card">
              <div className="text-center">
                <div className="mb-4 flex justify-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                    <FileCode size={32} className="text-muted-foreground" />
                  </div>
                </div>
                <h2 className="mb-2 text-lg font-semibold">Development Lab</h2>
                <p className="mb-6 max-w-md text-muted-foreground">
                  Monaco-based code editor with syntax highlighting. Create prompts, agent
                  logic, ontology definitions, and run experiments.
                </p>
                <button
                  onClick={handleNewFile}
                  className={cn(
                    'flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                    'hover:opacity-90'
                  )}
                >
                  <Plus size={16} />
                  New File
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Terminal panel */}
        <div className="h-48 border-t bg-zinc-900 text-zinc-100">
          <div className="flex h-8 items-center gap-2 border-b border-zinc-700 px-3">
            <Terminal size={14} />
            <span className="text-xs">Terminal</span>
          </div>
          <div className="p-3 font-mono text-xs">
            <span className="text-green-400">nexus@lab</span>
            <span className="text-zinc-500">:</span>
            <span className="text-blue-400">~</span>
            <span className="text-zinc-500">$</span>
            <span className="ml-2 animate-pulse">_</span>
          </div>
        </div>
      </div>
    </div>
    </>
  );
}
