'use client';

import { useEffect, useCallback, useState, useRef, useMemo } from 'react';
import {
  FileCode, Plus, Terminal, X, Save, GripHorizontal,
  Code, Eye, Columns2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';
import { useFilesStore, CODE_MY_DRIVE_FOLDER, resolveCodePath } from '@/stores/files';
import { useCodeStore } from '@/stores/code';
import { useWorkspaceStore } from '@/stores/workspace';
import { usePrompt } from '@/components/ui/dialogs';
import { Header } from '@/components/shell/header';
import Editor from '@monaco-editor/react';
import { getApiUrl } from '@/lib/config';
import { useAuthStore } from '@/stores/auth';

function getLanguage(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    py: 'python', js: 'javascript', ts: 'typescript', tsx: 'typescript',
    jsx: 'javascript', json: 'json', md: 'markdown', yaml: 'yaml', yml: 'yaml',
    html: 'html', css: 'css', scss: 'scss', sql: 'sql', sh: 'shell',
    bash: 'shell', zsh: 'shell', c: 'c', cpp: 'cpp', go: 'go', rs: 'rust',
    rb: 'ruby', php: 'php', toml: 'toml', ini: 'ini', env: 'plaintext',
    r: 'r', xml: 'xml', graphql: 'graphql', dockerfile: 'dockerfile',
  };
  return map[ext || ''] || 'plaintext';
}

// ─── Previews ─────────────────────────────────────────────────────────────────

type ViewMode = 'code' | 'preview' | 'split';

function HtmlPreview({ content }: { content: string }) {
  const blobUrl = useMemo(() => {
    const blob = new Blob([content], { type: 'text/html' });
    return URL.createObjectURL(blob);
  }, [content]);

  useEffect(() => () => URL.revokeObjectURL(blobUrl), [blobUrl]);

  return (
    <iframe
      key={blobUrl}
      src={blobUrl}
      className="h-full w-full border-0"
      sandbox="allow-scripts allow-same-origin"
      title="HTML preview"
    />
  );
}

function MarkdownPreview({ content }: { content: string }) {
  return (
    <div className="h-full w-full overflow-auto bg-background px-8 py-6">
      <article className="prose prose-sm dark:prose-invert max-w-3xl mx-auto
        [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mb-4 [&_h1]:mt-0
        [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mb-3 [&_h2]:mt-6
        [&_h3]:text-base [&_h3]:font-semibold [&_h3]:mb-2 [&_h3]:mt-4
        [&_p]:leading-relaxed [&_p]:mb-3
        [&_ul]:mb-3 [&_ol]:mb-3 [&_li]:mb-1
        [&_blockquote]:border-l-4 [&_blockquote]:border-border [&_blockquote]:pl-4 [&_blockquote]:text-muted-foreground
        [&_code]:bg-muted [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_code]:font-mono
        [&_pre]:bg-muted [&_pre]:rounded-lg [&_pre]:p-4 [&_pre]:overflow-x-auto
        [&_pre_code]:bg-transparent [&_pre_code]:p-0
        [&_table]:w-full [&_table]:border-collapse
        [&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-3 [&_th]:py-1.5 [&_th]:text-left [&_th]:text-sm
        [&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-1.5 [&_td]:text-sm
        [&_hr]:border-border [&_hr]:my-6
        [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </article>
    </div>
  );
}

// ─── Resizable terminal / logs panel ─────────────────────────────────────────

const MIN_H = 28;
const DEFAULT_H = 200;
const MAX_H = 600;

const XTERM_THEME = {
  background: '#1e1e1e', foreground: '#d4d4d4', cursor: '#d4d4d4',
  selectionBackground: '#264f78',
  black: '#1e1e1e',    brightBlack: '#808080',
  red: '#f44747',      brightRed: '#f44747',
  green: '#6a9955',    brightGreen: '#b5cea8',
  yellow: '#d7ba7d',   brightYellow: '#d7ba7d',
  blue: '#569cd6',     brightBlue: '#569cd6',
  magenta: '#c586c0',  brightMagenta: '#c586c0',
  cyan: '#4ec9b0',     brightCyan: '#4ec9b0',
  white: '#d4d4d4',    brightWhite: '#ffffff',
};

// ── PTY terminal (xterm.js connected to /api/terminal/ws) ─────────────────

// ── Shared xterm component ────────────────────────────────────────────────

interface XTermProps {
  wsPath: string;          // e.g. /api/terminal/ws or /api/logs/ws
  readonly?: boolean;
  scrollback?: number;
  onData?: (ws: WebSocket, data: string) => void;
  onMessage?: (term: import('@xterm/xterm').Terminal, e: MessageEvent) => void;
}

function XTermComponent({ wsPath, readonly = false, scrollback = 1000, onData, onMessage }: XTermProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let term: import('@xterm/xterm').Terminal;
    let ws: WebSocket;
    let ro: ResizeObserver;

    const init = async () => {
      const { Terminal } = await import('@xterm/xterm');
      const { FitAddon } = await import('@xterm/addon-fit');
      const { WebLinksAddon } = await import('@xterm/addon-web-links');
      if (!containerRef.current) return;

      term = new Terminal({
        cursorBlink: !readonly,
        disableStdin: readonly,
        fontFamily: '"JetBrains Mono", Menlo, Monaco, Consolas, monospace',
        fontSize: readonly ? 12 : 13,
        lineHeight: readonly ? 1.35 : 1.4,
        scrollback,
        theme: XTERM_THEME,
      });
      const fitAddon = new FitAddon();
      term.loadAddon(fitAddon);
      term.loadAddon(new WebLinksAddon());
      term.open(containerRef.current);
      fitAddon.fit();

      const token = useAuthStore.getState().token ?? '';
      const wsBase = getApiUrl().replace(/^http/, 'ws');
      ws = new WebSocket(`${wsBase}${wsPath}?token=${encodeURIComponent(token)}`);
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        if (!readonly) ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
      };
      ws.onmessage = onMessage
        ? (e) => onMessage(term, e)
        : (e) => term.write(e.data instanceof ArrayBuffer ? new Uint8Array(e.data) : String(e.data));
      ws.onclose = () => term.write('\r\n\x1b[2mConnection closed\x1b[0m\r\n');
      ws.onerror = () => term.write('\r\n\x1b[31mConnection failed\x1b[0m\r\n');

      if (!readonly) {
        term.onData((d) => {
          if (onData) { onData(ws, d); }
          else if (ws.readyState === WebSocket.OPEN) ws.send(new TextEncoder().encode(d));
        });
        term.onResize(({ cols, rows }) => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'resize', cols, rows }));
        });
      }

      ro = new ResizeObserver(() => { try { fitAddon.fit(); } catch { /* ignore */ } });
      ro.observe(containerRef.current!);
    };
    init();
    return () => { ro?.disconnect(); ws?.close(); term?.dispose(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={containerRef} className="h-full w-full overflow-hidden" />;
}

function XTerminalContent() {
  return <XTermComponent wsPath="/api/terminal/ws" />;
}

function LogsContent() {
  return (
    <XTermComponent
      wsPath="/api/logs/ws"
      readonly
      scrollback={5000}
      onMessage={(term, e) => { if (e.data) term.write(String(e.data)); }}
    />
  );
}

// ── Panel with Terminal / Logs tabs ──────────────────────────────────────

type PanelTab = 'terminal' | 'logs';

function TerminalPanel({ height, onResize }: { height: number; onResize: (h: number) => void }) {
  const dragging = useRef(false);
  const startY = useRef(0);
  const startH = useRef(0);
  const [tab, setTab] = useState<PanelTab>('terminal');

  const onMouseDown = (e: React.MouseEvent) => {
    dragging.current = true;
    startY.current = e.clientY;
    startH.current = height;
    e.preventDefault();
  };

  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (!dragging.current) return;
      onResize(Math.min(MAX_H, Math.max(MIN_H, startH.current + (startY.current - e.clientY))));
    };
    const up = () => { dragging.current = false; };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
  }, [onResize]);

  return (
    <div className="flex flex-col border-t border-border/50 bg-[#1e1e1e]" style={{ height }}>
      {/* Title bar / drag handle */}
      <div
        onMouseDown={onMouseDown}
        className="flex h-7 flex-shrink-0 cursor-row-resize items-center gap-0 border-b border-border/40 bg-[#252526] select-none"
      >
        {/* Tabs */}
        {([['terminal', Terminal, 'Terminal'], ['logs', Terminal, 'Logs']] as const).map(([id, , label]) => (
          <button
            key={id}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={() => setTab(id)}
            className={cn(
              'flex h-full items-center gap-1.5 border-r border-border/30 px-3 text-[11px] transition-colors',
              tab === id
                ? 'bg-[#1e1e1e] text-zinc-200'
                : 'text-zinc-500 hover:bg-[#2d2d2d] hover:text-zinc-300',
            )}
          >
            <Terminal size={11} />
            {label}
          </button>
        ))}
        <div className="flex-1" />
        <GripHorizontal size={12} className="mr-3 text-zinc-600" />
      </div>

      {height > MIN_H && (
        <div className="flex-1 overflow-hidden p-1">
          {tab === 'terminal' ? <XTerminalContent /> : <LogsContent />}
        </div>
      )}
    </div>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState({ onNewFile, sessionName }: { onNewFile: () => void; sessionName?: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-muted">
        <FileCode size={28} className="text-muted-foreground" />
      </div>
      <p className="mb-1 font-medium">{sessionName || 'No file open'}</p>
      <p className="mb-5 max-w-xs text-sm text-muted-foreground">
        Select a file from the explorer or use the AI assistant to generate one.
      </p>
      <button
        onClick={onNewFile}
        className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        <Plus size={15} />
        New File
      </button>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CodePage() {
  const {
    codeOpenFiles, codeActiveFile, codeFileContents, codeUnsavedChanges,
    setCodeActiveFile, closeCodeFile, setCodeFileContent, saveCodeFile, createCodeFile, openCodeFile,
    syncCodeWorkdir, fetchCodeFiles,
  } = useFilesStore();
  const { getActiveSession } = useCodeStore();
  const { setContextPanelOpen } = useWorkspaceStore();
  const { prompt, dialog: promptDialog } = usePrompt();
  const [terminalH, setTerminalH] = useState(MIN_H);
  const [viewMode, setViewMode] = useState<ViewMode>('code');

  const activeSession = getActiveSession();
  const activeContent = codeActiveFile ? codeFileContents[codeActiveFile] : undefined;
  const hasUnsaved = codeActiveFile ? codeUnsavedChanges[codeActiveFile] : false;
  const language = codeActiveFile ? getLanguage(codeActiveFile) : 'plaintext';
  const ext = codeActiveFile?.split('.').pop()?.toLowerCase() ?? '';
  const isHtml = ext === 'html' || ext === 'htm';
  const isMarkdown = ext === 'md' || ext === 'mdx';
  const hasPreview = isHtml || isMarkdown;

  // Auto-switch to split when opening a previewable file
  useEffect(() => {
    if (hasPreview) setViewMode('split');
    else setViewMode('code');
  }, [hasPreview]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-open the AI pane when entering Code
  useEffect(() => {
    setContextPanelOpen(true);
    return () => setContextPanelOpen(false);
  }, [setContextPanelOpen]);

  useEffect(() => {
    void syncCodeWorkdir('pull');
    void fetchCodeFiles(CODE_MY_DRIVE_FOLDER);
  }, [syncCodeWorkdir, fetchCodeFiles]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      if (codeActiveFile) saveCodeFile(codeActiveFile);
    }
  }, [codeActiveFile, saveCodeFile]);

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
      const path = resolveCodePath(name);
      const createdPath = await createCodeFile(path);
      if (createdPath) openCodeFile(createdPath);
    }
  };

  return (
    <>
      {promptDialog}
      <div className="flex h-full flex-col bg-background">
        <Header title={activeSession?.name || 'Code'} subtitle={activeSession?.rootPath || 'Development environment'} />

        {/* Tab bar */}
        <div className="flex h-8 flex-shrink-0 items-center gap-0.5 overflow-x-auto border-b border-border/50 bg-muted/20 px-1">
          {codeOpenFiles.map((path) => {
            const filename = path.split('/').pop() || path;
            const isActive = path === codeActiveFile;
            const isUnsaved = codeUnsavedChanges[path];
            return (
              <div key={path} onClick={() => setCodeActiveFile(path)}
                className={cn(
                  'group flex flex-shrink-0 items-center gap-1.5 rounded px-2.5 py-1 text-xs cursor-pointer transition-colors select-none',
                  isActive ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                <FileCode size={11} className={isActive ? 'text-workspace-accent' : 'text-muted-foreground/60'} />
                <span>{filename}</span>
                {isUnsaved && <span className="text-amber-400 text-[10px]">●</span>}
                <button onClick={(e) => { e.stopPropagation(); closeCodeFile(path); }}
                  className="ml-0.5 rounded p-0.5 opacity-0 hover:bg-muted group-hover:opacity-100 transition-opacity">
                  <X size={9} />
                </button>
              </div>
            );
          })}

          <button onClick={handleNewFile}
            className="ml-auto mr-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
            title="New file">
            <Plus size={12} />
          </button>
        </div>

        {/* Editor / preview area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {codeActiveFile && activeContent !== undefined ? (
            <div className="flex flex-1 flex-col overflow-hidden">
              {/* Breadcrumb + save */}
              <div className="flex h-6 flex-shrink-0 items-center justify-between border-b border-border/30 bg-muted/10 px-4">
                <span className="text-[11px] text-muted-foreground">{codeActiveFile}</span>
                <div className="flex items-center gap-2">
                  {hasUnsaved && (
                    <button onClick={() => saveCodeFile(codeActiveFile)}
                      className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] text-amber-500 hover:bg-muted">
                      <Save size={10} /> Save
                    </button>
                  )}
                  {hasPreview && (
                    <div className="flex items-center gap-0.5 rounded-md border border-border/60 bg-background p-0.5">
                      {([['code', Code, 'Code'], ['split', Columns2, 'Split'], ['preview', Eye, 'Preview']] as const).map(([mode, Icon, label]) => (
                        <button key={mode} onClick={() => setViewMode(mode)}
                          title={label}
                          className={cn(
                            'flex h-5 w-5 items-center justify-center rounded text-[10px] transition-colors',
                            viewMode === mode ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'
                          )}>
                          <Icon size={11} />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Content pane */}
              <div className={cn('flex flex-1 overflow-hidden', viewMode === 'split' && 'flex-row')}>
                {/* Monaco — hidden in preview-only mode */}
                {viewMode !== 'preview' && (
                  <div className={cn('overflow-hidden', viewMode === 'split' ? 'w-1/2 border-r border-border/50' : 'flex-1')}>
                    <Editor
                      height="100%"
                      language={language}
                      value={activeContent}
                      onChange={(v) => setCodeFileContent(codeActiveFile, v || '')}
                      theme="vs-dark"
                      options={{
                        fontSize: 13,
                        fontFamily: 'JetBrains Mono, Menlo, Monaco, Consolas, monospace',
                        minimap: { enabled: viewMode === 'code' },
                        scrollBeyondLastLine: false,
                        automaticLayout: true,
                        tabSize: 2,
                        wordWrap: 'on',
                        lineNumbers: 'on',
                        renderWhitespace: 'selection',
                        bracketPairColorization: { enabled: true },
                        padding: { top: 12 },
                        smoothScrolling: true,
                        cursorBlinking: 'smooth',
                        formatOnPaste: true,
                      }}
                      loading={
                        <div className="flex h-full items-center justify-center bg-[#1e1e1e]">
                          <span className="text-xs text-zinc-500">Loading editor...</span>
                        </div>
                      }
                    />
                  </div>
                )}

                {/* Preview — shown in preview or split mode */}
                {hasPreview && viewMode !== 'code' && (
                  <div className={cn('overflow-hidden', viewMode === 'split' ? 'w-1/2' : 'flex-1', isHtml ? 'bg-white' : 'bg-background')}>
                    {isHtml
                      ? <HtmlPreview content={activeContent} />
                      : <MarkdownPreview content={activeContent} />
                    }
                  </div>
                )}
              </div>
            </div>
          ) : (
            <EmptyState onNewFile={handleNewFile} sessionName={activeSession?.name} />
          )}
        </div>

        {/* Resizable terminal */}
        <TerminalPanel height={terminalH} onResize={setTerminalH} />
      </div>
    </>
  );
}
