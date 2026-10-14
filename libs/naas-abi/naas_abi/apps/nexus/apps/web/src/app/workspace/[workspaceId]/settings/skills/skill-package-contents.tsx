'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, FileCode, FileText, Folder, Trash2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input, Textarea } from '@/components/ui/input';

/**
 * Real files on a skill package. Postgres prompt rows pass an empty list
 * and this renders nothing, so they never get a fake tree.
 */
type FileNode = { type: 'file'; name: string; path: string };
type DirNode = { type: 'dir'; name: string; path: string; children: TreeNode[] };
type TreeNode = FileNode | DirNode;

function compareNodes(a: TreeNode, b: TreeNode): number {
  const aSkill = a.type === 'file' && a.name === 'SKILL.md';
  const bSkill = b.type === 'file' && b.name === 'SKILL.md';
  if (aSkill !== bSkill) return aSkill ? -1 : 1;
  if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
  return a.name.localeCompare(b.name);
}

function buildTree(files: string[]): TreeNode[] {
  const root: DirNode = { type: 'dir', name: '', path: '', children: [] };
  for (const file of files) {
    const parts = file.split('/').filter(Boolean);
    if (parts.length === 0) continue;
    let cursor = root;
    for (let index = 0; index < parts.length; index += 1) {
      const name = parts[index];
      const path = parts.slice(0, index + 1).join('/');
      const isFile = index === parts.length - 1;
      if (isFile) {
        cursor.children.push({ type: 'file', name, path });
        continue;
      }
      let dir = cursor.children.find(
        (child): child is DirNode => child.type === 'dir' && child.name === name,
      );
      if (!dir) {
        dir = { type: 'dir', name, path, children: [] };
        cursor.children.push(dir);
      }
      cursor = dir;
    }
  }
  const sortLevel = (nodes: TreeNode[]) => {
    nodes.sort(compareNodes);
    for (const node of nodes) {
      if (node.type === 'dir') sortLevel(node.children);
    }
  };
  sortLevel(root.children);
  return root.children;
}

function isMarkdownPath(path: string): boolean {
  return path.toLowerCase().endsWith('.md');
}

const MARKDOWN_CLASS = [
  'max-w-none px-4 py-4 text-sm leading-6 text-foreground',
  '[&>*:first-child]:mt-0 [&>*:last-child]:mb-0',
  '[&_h1]:mb-3 [&_h1]:mt-0 [&_h1]:border-b [&_h1]:border-border [&_h1]:pb-2 [&_h1]:text-lg [&_h1]:font-semibold',
  '[&_h2]:mb-2 [&_h2]:mt-5 [&_h2]:border-b [&_h2]:border-border [&_h2]:pb-1 [&_h2]:text-base [&_h2]:font-semibold',
  '[&_h3]:mb-2 [&_h3]:mt-4 [&_h3]:text-sm [&_h3]:font-semibold',
  '[&_p]:my-2',
  '[&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5',
  '[&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5',
  '[&_li]:my-1',
  '[&_a]:text-primary [&_a]:underline',
  '[&_code]:bg-muted [&_code]:px-1 [&_code]:font-mono [&_code]:text-xs',
  '[&_pre]:my-3 [&_pre]:overflow-auto [&_pre]:border [&_pre]:border-border [&_pre]:bg-muted [&_pre]:p-3 [&_pre]:font-mono [&_pre]:text-xs',
  '[&_pre_code]:bg-transparent [&_pre_code]:p-0',
  '[&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground',
  '[&_table]:my-3 [&_table]:w-full [&_table]:border-collapse [&_table]:text-xs',
  '[&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:font-medium',
  '[&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_td]:align-top',
].join(' ');

export type SkillFileEditor = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
};

export function SkillPackageContents({
  files,
  selectedPath,
  selectedText,
  onSelect,
  fileEditor,
  onAddFile,
  onRemoveFile,
}: {
  files: string[];
  selectedPath: string | null;
  selectedText: string | null;
  onSelect: (path: string) => void;
  /** Create mode: edit the selected file instead of previewing it. */
  fileEditor?: SkillFileEditor | null;
  /** Returns an error message, or null when the path was added. */
  onAddFile?: (path: string) => string | null;
  onRemoveFile?: (path: string) => void;
}) {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => new Set());
  if (files.length === 0) return null;

  const tree = buildTree(files);
  const toggle = (path: string) => {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const renderNodes = (nodes: TreeNode[], depth: number) => (
    <ul role={depth === 0 ? 'tree' : 'group'} aria-label={depth === 0 ? 'Skill files' : undefined}>
      {nodes.map((node) => {
        const selected = node.type === 'file' && node.path === selectedPath;
        if (node.type === 'dir') {
          const open = !collapsed.has(node.path);
          return (
            <li key={node.path} role="none">
              <button
                type="button"
                role="treeitem"
                aria-expanded={open}
                data-folder={node.name}
                data-path={node.path}
                className="flex w-full items-center gap-1.5 py-1 pr-2 text-left text-sm text-foreground hover:bg-muted"
                style={{ paddingLeft: `${8 + depth * 16}px` }}
                onClick={() => toggle(node.path)}
              >
                {open ? (
                  <ChevronDown size={14} className="shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight size={14} className="shrink-0 text-muted-foreground" />
                )}
                <Folder size={14} className="shrink-0 text-muted-foreground" />
                <span className="truncate">{node.name}/</span>
              </button>
              {open ? renderNodes(node.children, depth + 1) : null}
            </li>
          );
        }
        const Icon = node.path.toLowerCase().endsWith('.py') ? FileCode : FileText;
        const removable = Boolean(onRemoveFile) && node.path !== 'SKILL.md';
        return (
          <li key={node.path} role="none" className="flex items-stretch">
            <button
              type="button"
              role="treeitem"
              data-path={node.path}
              aria-current={selected ? 'true' : undefined}
              className={cn(
                'flex min-w-0 flex-1 items-center gap-1.5 py-1 pr-2 text-left text-sm hover:bg-muted',
                selected ? 'bg-primary/10 text-primary' : 'text-foreground',
              )}
              style={{ paddingLeft: `${8 + depth * 16}px` }}
              onClick={() => onSelect(node.path)}
            >
              <span className="inline-block w-3.5 shrink-0" />
              <Icon size={14} className={cn('shrink-0', selected ? 'text-primary' : 'text-muted-foreground')} />
              <span className="truncate">{node.name}</span>
            </button>
            {removable ? (
              <button
                type="button"
                aria-label={`Remove ${node.path}`}
                title="Remove file"
                className="px-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                onClick={() => onRemoveFile?.(node.path)}
              >
                <Trash2 size={12} />
              </button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );

  return (
    <section aria-label="Contents" className="border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">
          Contents
          <span className="ml-2 font-normal text-muted-foreground">· {files.length}</span>
        </h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-[240px_minmax(0,1fr)]">
        <nav className="flex max-h-80 flex-col border-b border-border md:max-h-[32rem] md:border-b-0 md:border-r">
          <div className="min-h-0 flex-1 overflow-auto py-1">{renderNodes(tree, 0)}</div>
          {onAddFile ? <AddSkillFile onAddFile={onAddFile} /> : null}
        </nav>
        <div className="min-w-0">
          {selectedPath ? (
            <div className="border-b border-border px-4 py-2 font-mono text-xs text-muted-foreground">
              {selectedPath}
            </div>
          ) : null}
          <div className="max-h-96 overflow-auto md:max-h-[30rem]">
            {fileEditor ? (
              <Textarea
                value={fileEditor.value}
                onChange={(event) => fileEditor.onChange(event.target.value)}
                placeholder={fileEditor.placeholder}
                aria-label={selectedPath ? `Edit ${selectedPath}` : 'Edit file'}
                rows={16}
                className="min-h-80 w-full resize-y border-0 bg-transparent px-4 py-4 font-mono text-sm leading-6 shadow-none focus-visible:ring-0"
              />
            ) : !selectedPath ? (
              <p className="px-4 py-4 text-sm text-muted-foreground">Select a file.</p>
            ) : selectedText == null ? (
              <p className="px-4 py-4 text-sm text-muted-foreground">Loading…</p>
            ) : isMarkdownPath(selectedPath) ? (
              <div data-testid="skill-file-body" className={MARKDOWN_CLASS}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedText}</ReactMarkdown>
              </div>
            ) : (
              <pre
                data-testid="skill-file-body"
                className="overflow-auto whitespace-pre px-4 py-4 font-mono text-xs leading-5 text-foreground"
              >
                {selectedText}
              </pre>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function AddSkillFile({ onAddFile }: { onAddFile: (path: string) => string | null }) {
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <div className="border-t border-border">
        <button
          type="button"
          className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
          onClick={() => setOpen(true)}
        >
          + Add file
        </button>
      </div>
    );
  }

  return (
    <form
      className="grid gap-1.5 border-t border-border p-2"
      onSubmit={(event) => {
        event.preventDefault();
        const message = onAddFile(path);
        if (message) {
          setError(message);
          return;
        }
        setPath('');
        setError(null);
        setOpen(false);
      }}
    >
      <Input
        value={path}
        onChange={(event) => setPath(event.target.value)}
        placeholder="references/notes.md"
        aria-label="File path"
        className="font-mono"
        autoFocus
      />
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
      <div className="flex justify-end gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            setOpen(false);
            setPath('');
            setError(null);
          }}
        >
          Cancel
        </Button>
        <Button type="submit" size="sm">
          Add
        </Button>
      </div>
    </form>
  );
}
