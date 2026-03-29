'use client';

import React, { useEffect, useCallback, useState, useRef } from 'react';
import dynamic from 'next/dynamic';
import { useTheme } from 'next-themes';
import { Header } from '@/components/shell/header';
import { FileCode, Plus, X, Save, Eye, Code, Columns2, RefreshCw, Maximize2, TerminalSquare } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFilesStore } from '@/stores/files';
import { usePrompt } from '@/components/ui/dialogs';
import { useWorkspaceStore } from '@/stores/workspace';
import type { AgentType } from '@/stores/workspace';
import { getApiUrl } from '@/lib/config';
import Editor from '@monaco-editor/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// xterm.js uses browser APIs — must be client-only
const TerminalPane = dynamic(
  () => import('@/components/shell/terminal-pane').then((m) => ({ default: m.TerminalPane })),
  { ssr: false }
);

type MdView = 'edit' | 'preview' | 'split';
type HtmlView = 'edit' | 'preview' | 'split';

function getLanguage(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();
  const languageMap: Record<string, string> = {
    py: 'python', js: 'javascript', ts: 'typescript', tsx: 'typescript',
    jsx: 'javascript', json: 'json', md: 'markdown', yaml: 'yaml', yml: 'yaml',
    html: 'html', css: 'css', scss: 'scss', less: 'less', sql: 'sql',
    sh: 'shell', bash: 'shell', zsh: 'shell', c: 'c', cpp: 'cpp', h: 'c',
    hpp: 'cpp', java: 'java', go: 'go', rs: 'rust', rb: 'ruby', php: 'php',
    swift: 'swift', kt: 'kotlin', scala: 'scala', r: 'r', xml: 'xml',
    graphql: 'graphql', dockerfile: 'dockerfile', toml: 'toml', ini: 'ini',
    env: 'plaintext',
  };
  return languageMap[ext || ''] || 'plaintext';
}

function isMarkdown(path: string) {
  return path.endsWith('.md') || path.endsWith('.mdx');
}

function isHtml(path: string) {
  return path.endsWith('.html') || path.endsWith('.htm');
}

// ─── Markdown preview ─────────────────────────────────────────────────────────
const MD_STYLES = `
.md-body { font-size: 14px; line-height: 1.7; color: inherit; }
.md-body h1,.md-body h2,.md-body h3,.md-body h4,.md-body h5,.md-body h6 {
  font-weight: 600; letter-spacing: -0.01em; margin: 1.4em 0 0.5em; line-height: 1.3; }
.md-body h1 { font-size: 1.75em; border-bottom: 1px solid hsl(var(--border)); padding-bottom: 0.3em; }
.md-body h2 { font-size: 1.4em; border-bottom: 1px solid hsl(var(--border)); padding-bottom: 0.2em; }
.md-body h3 { font-size: 1.15em; }
.md-body h4 { font-size: 1em; }
.md-body p { margin: 0.75em 0; }
.md-body a { color: #2563eb; text-decoration: none; }
.md-body a:hover { text-decoration: underline; }
.dark .md-body a { color: #60a5fa; }
.md-body strong { font-weight: 600; }
.md-body em { font-style: italic; }
.md-body code {
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 0.85em;
  background: hsl(var(--muted));
  border-radius: 4px;
  padding: 0.15em 0.4em;
}
.md-body pre {
  background: hsl(var(--muted) / 0.6);
  border: 1px solid hsl(var(--border));
  border-radius: 8px;
  padding: 1em 1.2em;
  overflow-x: auto;
  margin: 1em 0;
}
.md-body pre code {
  background: none;
  padding: 0;
  font-size: 0.88em;
  line-height: 1.6;
}
.md-body blockquote {
  border-left: 3px solid hsl(var(--muted-foreground) / 0.4);
  margin: 1em 0;
  padding: 0.2em 1em;
  color: hsl(var(--muted-foreground));
}
.md-body ul,.md-body ol { margin: 0.6em 0; padding-left: 1.6em; }
.md-body li { margin: 0.3em 0; }
.md-body ul { list-style-type: disc; }
.md-body ol { list-style-type: decimal; }
.md-body ul li input[type=checkbox] { margin-right: 0.4em; accent-color: hsl(var(--primary)); }
.md-body table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
  font-size: 0.9em;
}
.md-body th,.md-body td {
  border: 1px solid hsl(var(--border));
  padding: 6px 12px;
  text-align: left;
}
.md-body th { background: hsl(var(--muted) / 0.5); font-weight: 600; }
.md-body tr:nth-child(even) { background: hsl(var(--muted) / 0.2); }
.md-body img { max-width: 100%; border-radius: 8px; border: 1px solid hsl(var(--border)); margin: 0.5em 0; }
.md-body hr { border: none; border-top: 1px solid hsl(var(--border)); margin: 1.5em 0; }
`;

function MarkdownPreview({ content }: { content: string }) {
  return (
    <div className="h-full overflow-y-auto">
      <style>{MD_STYLES}</style>
      <div className="md-body px-8 py-6 max-w-4xl">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ href, children, ...props }) => (
              <a href={href} target="_blank" rel="noopener noreferrer" {...props}>{children}</a>
            ),
            input: ({ ...props }) => <input {...props} className="mr-1.5" />,
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}

// ─── Markdown toolbar ─────────────────────────────────────────────────────────
function MdViewToggle({ view, onChange }: { view: MdView; onChange: (v: MdView) => void }) {
  return (
    <div className="flex items-center rounded border bg-muted/30 p-0.5">
      {([
        ['edit',    <Code    size={12} key="e" />, 'Edit'],
        ['split',   <Columns2 size={12} key="s" />, 'Split'],
        ['preview', <Eye     size={12} key="p" />, 'Preview'],
      ] as [MdView, React.ReactNode, string][]).map(([v, icon, label]) => (
        <button
          key={v}
          onClick={() => onChange(v)}
          title={label}
          className={cn(
            'flex items-center gap-1 rounded px-2 py-0.5 text-[11px] transition-colors',
            view === v
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          {icon}
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}

// ─── HTML / Slides preview ─────────────────────────────────────────────────────

/** Universal scaler injected into every HTML preview.
 *  Handles both slide-wrapper variant (web-slides) and bare .slide variant (apps/slides).
 *  Overrides any built-in scaleSlides so behaviour is consistent inside the iframe. */
const AIA_SCALER_SCRIPT = `
<style id="aia-preview-reset">
  *, *::before, *::after { box-sizing: border-box; }
  html { overflow-x: hidden; }
  body { margin: 0 !important; padding: 4px 0 !important; overflow-x: hidden; background: #f5f5f5; }
  .slide-wrapper {
    width: 100% !important; max-width: 100% !important;
    margin: 4px 0 !important; position: relative !important; overflow: hidden !important;
  }
  .slide { transform-origin: top left !important; }
</style>
<script id="aia-scaler">
(function () {
  function rescale() {
    var wrappers = document.querySelectorAll('.slide-wrapper');
    if (wrappers.length) {
      wrappers.forEach(function (w) {
        var slide = w.querySelector('.slide');
        if (!slide) return;
        var cw = w.clientWidth || w.offsetWidth || 1280;
        var s = cw / 1280;
        slide.style.transform = 'scale(' + s + ')';
        slide.style.transformOrigin = 'top left';
        w.style.height = Math.round(720 * s) + 'px';
        w.style.paddingBottom = '0';
      });
    } else {
      /* bare .slide variant (apps/slides — no wrapper) */
      var vw = document.documentElement.clientWidth || 1280;
      document.querySelectorAll('.slide').forEach(function (slide) {
        var s = vw / 1280;
        slide.style.transform = 'scale(' + s + ')';
        slide.style.transformOrigin = 'top left';
        slide.style.display = 'block';
        slide.style.marginBottom = Math.round((720 * s) - 720 + 8) + 'px';
      });
    }
  }
  /* Override any built-in scaleSlides defined later in the file */
  window.scaleSlides = rescale;
  requestAnimationFrame(rescale);
  window.addEventListener('resize', rescale);
  document.addEventListener('DOMContentLoaded', function () { requestAnimationFrame(rescale); });
})();
</script>
`;

/** Fetches relative CSS hrefs, inlines them, then injects the universal scaler. */
async function prepareHtmlPreview(html: string, filePath: string): Promise<string> {
  const dir = filePath.split('/').slice(0, -1).join('/');
  const store = useFilesStore.getState();
  const apiBase = getApiUrl();

  // Inline relative <link rel="stylesheet" href="...">
  const linkRe = /<link[^>]+href="([^"]+\.css)"[^>]*\/?>/gi;
  let result = html;
  for (const match of [...html.matchAll(linkRe)]) {
    const href = match[1];
    if (/^https?:\/\/|^\/\//.test(href)) continue;
    const cssPath = dir ? `${dir}/${href}` : href;
    try {
      const cssContent = await store.readHostFile(cssPath);
      result = result.replace(match[0], `<style>/* ${href} */\n${cssContent}</style>`);
    } catch { /* leave original link tag */ }
  }

  // Inject <base href> so relative image/font paths resolve via the raw-serve API.
  // This must come before AIA_SCALER_SCRIPT so it's the first thing in <head>.
  const baseHref = `${apiBase}/api/lab/fs/raw/${dir}/`;
  const baseTag = `<base href="${baseHref}" />\n`;

  // Inject scaler: right after <head> open (so it's defined before any inline scripts)
  if (result.includes('<head>')) {
    result = result.replace('<head>', '<head>\n' + baseTag + AIA_SCALER_SCRIPT);
  } else if (result.includes('<head ')) {
    result = result.replace(/<head(\s[^>]*)?>/, (m) => m + '\n' + baseTag + AIA_SCALER_SCRIPT);
  } else {
    result = baseTag + AIA_SCALER_SCRIPT + result;
  }

  return result;
}

function HtmlPreview({ srcdoc, previewKey, onRefresh }: { srcdoc: string; previewKey: number; onRefresh: () => void }) {
  return (
    <div className="relative flex flex-1 flex-col overflow-hidden bg-[#f5f5f5]">
      {/* Toolbar overlay */}
      <div className="absolute right-2 top-2 z-10 flex items-center gap-1">
        <button
          onClick={onRefresh}
          title="Reload preview (re-inlines CSS)"
          className="flex items-center gap-1 rounded bg-black/10 px-2 py-0.5 text-[10px] text-black/60 hover:bg-black/20"
        >
          <RefreshCw size={10} /> Reload
        </button>
        <button
          onClick={() => {
            const w = window.open('about:blank', '_blank');
            if (w) { w.document.write(srcdoc); w.document.close(); }
          }}
          title="Open full-screen in new tab"
          className="flex items-center gap-1 rounded bg-black/10 px-2 py-0.5 text-[10px] text-black/60 hover:bg-black/20"
        >
          <Maximize2 size={10} /> Full
        </button>
      </div>
      <iframe
        key={previewKey}
        srcDoc={srcdoc || '<p style="font-family:sans-serif;color:#888;padding:2rem">Preparing preview…</p>'}
        className="flex-1 w-full border-0"
        sandbox="allow-scripts allow-same-origin"
        title="HTML / Slides Preview"
        style={{ height: '100%' }}
      />
    </div>
  );
}

function HtmlViewToggle({ view, onChange }: { view: HtmlView; onChange: (v: HtmlView) => void }) {
  return (
    <div className="flex items-center rounded border bg-muted/30 p-0.5">
      {([
        ['edit',    <Code    size={12} key="e" />, 'Edit'],
        ['split',   <Columns2 size={12} key="s" />, 'Split'],
        ['preview', <Eye     size={12} key="p" />, 'Slides'],
      ] as [HtmlView, React.ReactNode, string][]).map(([v, icon, label]) => (
        <button
          key={v}
          onClick={() => onChange(v)}
          title={label}
          className={cn(
            'flex items-center gap-1 rounded px-2 py-0.5 text-[11px] transition-colors',
            view === v
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          {icon}
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────
export default function LabPage() {
  const { resolvedTheme } = useTheme();
  const monacoTheme = resolvedTheme === 'dark' ? 'vs-dark' : 'light';
  const [mdView, setMdView] = useState<MdView>('preview');
  const [htmlView, setHtmlView] = useState<HtmlView>('split');
  const [htmlSrcdoc, setHtmlSrcdoc] = useState<string>('');
  const [srcdocKey, setSrcdocKey] = useState(0);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [terminalHeight, setTerminalHeight] = useState(220);
  const dragRef = useRef<{ startY: number; startH: number } | null>(null);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    dragRef.current = { startY: e.clientY, startH: terminalHeight };
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      const delta = dragRef.current.startY - ev.clientY;
      setTerminalHeight(Math.max(100, Math.min(600, dragRef.current.startH + delta)));
    };
    const onUp = () => {
      dragRef.current = null;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [terminalHeight]);

  const {
    openFiles, activeFile, fileContents, unsavedChanges,
    setActiveFile, closeFile, setFileContent, saveHostFile, openFile,
  } = useFilesStore();
  const { prompt, dialog: promptDialog } = usePrompt();

  // Switch to preview when opening a markdown file, edit for code
  const prevActiveFile = useRef<string | null>(null);
  useEffect(() => {
    if (activeFile && activeFile !== prevActiveFile.current) {
      prevActiveFile.current = activeFile;
      if (isMarkdown(activeFile)) {
        setMdView('preview');
      } else if (isHtml(activeFile)) {
        setHtmlView('split');
      }
    }
  }, [activeFile]);

  // Auto-open AI pane
  useEffect(() => {
    const { contextPanelOpen, toggleContextPanel, setPaneAgent } = useWorkspaceStore.getState();
    if (!contextPanelOpen) toggleContextPanel();
    setPaneAgent('opencode' as AgentType);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      if (activeFile) saveHostFile(activeFile);
    }
  }, [activeFile, saveHostFile]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const handleNewFile = async () => {
    const name = await prompt({
      title: 'New File',
      description: 'Enter path relative to ~/aia (e.g. src/mymodule/app.py)',
      defaultValue: 'src/untitled.py',
      confirmLabel: 'Create',
    });
    if (name) {
      const store = useFilesStore.getState();
      store.setFileContent(name, '');
      await store.saveHostFile(name);
      openFile(name);
      await store.refreshLabFiles();
    }
  };

  const activeContent = activeFile ? (fileContents[activeFile] ?? '') : undefined;
  const hasUnsavedChanges = activeFile ? unsavedChanges[activeFile] : false;
  const language = activeFile ? getLanguage(activeFile) : 'plaintext';
  const isMd = activeFile ? isMarkdown(activeFile) : false;
  const isHtmlFile = activeFile ? isHtml(activeFile) : false;

  // Build inlined srcdoc whenever HTML file content changes or reload is triggered
  useEffect(() => {
    if (!isHtmlFile || !activeFile || activeContent === undefined) return;
    prepareHtmlPreview(activeContent, activeFile).then((doc) => {
      setHtmlSrcdoc(doc);
      setSrcdocKey((k) => k + 1); // force iframe remount with fresh content
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeContent, activeFile, isHtmlFile]);

  const editorPanel = activeFile && activeContent !== undefined && (
    <div className="flex flex-1 flex-col overflow-hidden">
      <Editor
        height="100%"
        language={language}
        value={activeContent}
        onChange={(value) => setFileContent(activeFile, value || '')}
        theme={monacoTheme}
        options={{
          fontSize: 14,
          fontFamily: 'JetBrains Mono, Menlo, Monaco, Consolas, monospace',
          minimap: { enabled: !isMd },
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
          <div className="flex h-full items-center justify-center">
            <span className="text-sm text-muted-foreground">Loading editor...</span>
          </div>
        }
      />
    </div>
  );

  const previewPanel = activeFile && activeContent !== undefined && (
    <div className="flex flex-1 flex-col overflow-hidden border-l">
      <MarkdownPreview content={activeContent} />
    </div>
  );

  return (
    <>
      {promptDialog}
      <div className="flex h-full flex-col">
        <Header title="Lab" subtitle="Development environment" />

        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Tabs bar */}
          <div className="flex h-10 items-center gap-1 border-b bg-muted/30 px-2">
            <button
              onClick={handleNewFile}
              className="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <Plus size={13} />
              New file
            </button>
            <div className="mx-1 h-4 w-px bg-border" />
            <div className="flex flex-1 items-center gap-1 overflow-x-auto">
              {openFiles.map((path) => {
                const filename = path.split('/').pop() || path;
                const isActive = path === activeFile;
                const isUnsaved = unsavedChanges[path];
                return (
                  <div
                    key={path}
                    onClick={() => setActiveFile(path)}
                    className={cn(
                      'group flex shrink-0 items-center gap-2 rounded-md px-3 py-1 text-sm cursor-pointer transition-colors',
                      isActive ? 'bg-background' : 'hover:bg-background/50'
                    )}
                  >
                    <FileCode size={14} />
                    <span className={cn(isUnsaved && 'italic')}>
                      {filename}{isUnsaved && ' •'}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); closeFile(path); }}
                      className="rounded p-0.5 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100"
                    >
                      <X size={12} />
                    </button>
                  </div>
                );
              })}
            </div>
            {/* Terminal toggle */}
            <button
              onClick={() => setTerminalOpen((v) => !v)}
              title="Toggle terminal (bash)"
              className={cn(
                'ml-auto flex items-center gap-1.5 rounded px-2 py-1 text-xs transition-colors',
                terminalOpen
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <TerminalSquare size={14} />
              <span className="hidden sm:inline">Terminal</span>
            </button>
          </div>

          {/* Toolbar (breadcrumb + view toggle + save) */}
          {activeFile && activeContent !== undefined && (
            <div className="flex h-8 items-center justify-between border-b bg-muted/20 px-3">
              <span className="text-xs text-muted-foreground truncate">{activeFile}</span>
              <div className="flex items-center gap-2 shrink-0 ml-2">
                {isMd && <MdViewToggle view={mdView} onChange={setMdView} />}
                {isHtmlFile && <HtmlViewToggle view={htmlView} onChange={setHtmlView} />}
                {hasUnsavedChanges && (
                  <button
                    onClick={() => saveHostFile(activeFile)}
                    className="flex items-center gap-1 rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <Save size={12} />
                    Save
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Editor area */}
          <div className="flex flex-1 overflow-hidden">
            {activeFile && activeContent !== undefined ? (
              isMd ? (
                // Markdown: edit / split / preview
                <div className="flex flex-1 overflow-hidden">
                  {(mdView === 'edit' || mdView === 'split') && editorPanel}
                  {(mdView === 'preview' || mdView === 'split') && previewPanel}
                </div>
              ) : isHtmlFile ? (
                // HTML / Slides: edit / split / preview
                <div className="flex flex-1 overflow-hidden">
                  {(htmlView === 'edit' || htmlView === 'split') && editorPanel}
                  {(htmlView === 'preview' || htmlView === 'split') && (
                    <div className="flex flex-1 flex-col overflow-hidden border-l">
                      <HtmlPreview
                        srcdoc={htmlSrcdoc}
                        previewKey={srcdocKey}
                        onRefresh={() => {
                          if (activeFile && activeContent !== undefined) {
                            prepareHtmlPreview(activeContent, activeFile).then((doc) => {
                              setHtmlSrcdoc(doc);
                              setSrcdocKey((k) => k + 1);
                            });
                          }
                        }}
                      />
                    </div>
                  )}
                </div>
              ) : (
                // Code file: editor only
                <div className="flex flex-1 overflow-hidden">
                  {editorPanel}
                </div>
              )
            ) : (
              <div className="flex flex-1 items-center justify-center bg-card">
                <div className="text-center">
                  <div className="mb-4 flex justify-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                      <FileCode size={32} className="text-muted-foreground" />
                    </div>
                  </div>
                  <h2 className="mb-2 text-lg font-semibold">Development Lab</h2>
                  <p className="mb-6 max-w-md text-muted-foreground">
                    Monaco editor with syntax highlighting. Use the AI pane on the right to generate,
                    edit, and reason about code.
                  </p>
                  <button
                    onClick={handleNewFile}
                    className={cn(
                      'flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white mx-auto',
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

          {/* ── Terminal panel ─────────────────────────────────── */}
          {terminalOpen && (
            <div className="flex flex-col border-t" style={{ height: terminalHeight }}>
              {/* Drag handle */}
              <div
                onMouseDown={onDragStart}
                className="h-1 w-full cursor-row-resize bg-border/50 hover:bg-primary/40 transition-colors"
                title="Drag to resize"
              />
              <div className="flex-1 overflow-hidden">
                <TerminalPane visible={terminalOpen} />
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
