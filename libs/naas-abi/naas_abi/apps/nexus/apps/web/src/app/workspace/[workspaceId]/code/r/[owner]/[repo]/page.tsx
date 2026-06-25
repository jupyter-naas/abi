'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ChevronRight,
  Copy,
  File as FileIcon,
  Folder,
  GitBranch,
  History,
  Loader2,
  UploadCloud,
} from 'lucide-react';
import { authFetch } from '@/stores/auth';

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const s = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

interface Entry {
  name: string;
  path: string;
  type: 'file' | 'dir';
  size: number;
}
interface FileContent {
  path: string;
  name: string;
  size: number;
  text: string | null;
  is_binary: boolean;
}
interface Branch {
  name: string;
  protected: boolean;
}
interface Commit {
  sha: string;
  message: string;
  author: string;
  date: string | null;
}

export default function RepoCodePage() {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const owner = typeof params?.owner === 'string' ? params.owner : '';
  const repo = typeof params?.repo === 'string' ? params.repo : '';
  const repoId = `${owner}/${repo}`;
  const codeBase = `/workspace/${workspaceId}/code`;
  const q = `workspace_id=${encodeURIComponent(workspaceId)}&repo_id=${encodeURIComponent(repoId)}`;

  const [branches, setBranches] = useState<Branch[]>([]);
  const [ref, setRef] = useState('');
  const [path, setPath] = useState('');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [file, setFile] = useState<FileContent | null>(null);
  const [readme, setReadme] = useState<string | null>(null);
  const [cloneUrl, setCloneUrl] = useState('');
  const [empty, setEmpty] = useState(false);
  const [latest, setLatest] = useState<Commit | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Resolve branches + clone url + default ref once.
  useEffect(() => {
    if (!workspaceId || !repoId) return;
    void (async () => {
      try {
        const [bRes, rRes] = await Promise.all([
          authFetch(`/api/coding-environments/branches?${q}`),
          authFetch(`/api/coding-environments/repos?workspace_id=${encodeURIComponent(workspaceId)}`),
        ]);
        const bs = bRes.ok ? ((await bRes.json()) as Branch[]) : [];
        setBranches(bs);
        if (rRes.ok) {
          const repos = (await rRes.json()) as Array<{
            repo_id: string;
            clone_url: string;
            default_branch: string;
            empty: boolean;
          }>;
          const m = repos.find((r) => r.repo_id === repoId);
          if (m) {
            setCloneUrl(m.clone_url);
            setEmpty(m.empty);
            setRef((prev) => prev || m.default_branch || bs[0]?.name || 'main');
          }
        }
      } catch (e) {
        setError((e as Error).message);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, repoId]);

  const loadDir = useCallback(
    async (dirPath: string, atRef: string) => {
      setLoading(true);
      setFile(null);
      try {
        const res = await authFetch(
          `/api/coding-environments/repo-contents?${q}&path=${encodeURIComponent(dirPath)}&ref=${encodeURIComponent(atRef)}`,
        );
        const data = res.ok ? ((await res.json()) as Entry[]) : [];
        setEntries(data);
        const readmeEntry = data.find((e) => e.type === 'file' && /^readme\.md$/i.test(e.name));
        if (readmeEntry) {
          const fr = await authFetch(
            `/api/coding-environments/repo-file?${q}&path=${encodeURIComponent(readmeEntry.path)}&ref=${encodeURIComponent(atRef)}`,
          );
          setReadme(fr.ok ? ((await fr.json()) as FileContent).text : null);
        } else {
          setReadme(null);
        }
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [q],
  );

  useEffect(() => {
    if (ref) void loadDir(path, ref);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref, path]);

  // Latest commit on this branch — the GitHub-style header above the files.
  useEffect(() => {
    if (!ref) return;
    void (async () => {
      try {
        const res = await authFetch(
          `/api/coding-environments/repo-commits?${q}&ref=${encodeURIComponent(ref)}&limit=1`,
        );
        const data = res.ok ? ((await res.json()) as Commit[]) : [];
        setLatest(data[0] ?? null);
      } catch {
        setLatest(null);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref]);

  const openFile = async (entry: Entry) => {
    setLoading(true);
    try {
      const res = await authFetch(
        `/api/coding-environments/repo-file?${q}&path=${encodeURIComponent(entry.path)}&ref=${encodeURIComponent(ref)}`,
      );
      if (res.ok) setFile((await res.json()) as FileContent);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // Local Forgejo serves a self-signed cert, so a clone against a *.localhost
  // host needs TLS verification turned off for that one command.
  const insecureClone = /localhost/i.test(cloneUrl);
  const cloneCmd = cloneUrl
    ? `git clone ${insecureClone ? '-c http.sslVerify=false ' : ''}${cloneUrl}`
    : '';

  const copyClone = async () => {
    try {
      await navigator.clipboard.writeText(cloneCmd);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  const crumbs = path ? path.split('/') : [];

  if (empty) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="max-w-md space-y-3 text-center">
          <UploadCloud size={28} className="mx-auto text-workspace-accent" />
          <h2 className="text-sm font-medium">This repository is empty</h2>
          <p className="text-xs text-muted-foreground">
            Push your code to get started — the Branches tab has the clone URL, a generated
            token, and ready-to-paste commands.
          </p>
          <Link
            href={`${codeBase}/r/${repoId}/branches`}
            className="inline-flex items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
          >
            Set up & push
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-border/50 px-4 py-2">
        <div className="flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs">
          <GitBranch size={13} className="text-muted-foreground" />
          <select
            value={ref}
            onChange={(e) => {
              setPath('');
              setRef(e.target.value);
            }}
            className="bg-transparent outline-none"
          >
            {branches.map((b) => (
              <option key={b.name} value={b.name}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div className="ml-auto flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs">
          <span className="text-muted-foreground">Clone</span>
          <code title={cloneCmd} className="max-w-[360px] truncate font-mono">
            {cloneCmd}
          </code>
          <button
            onClick={copyClone}
            title="Copy clone command"
            className="flex-shrink-0 text-muted-foreground hover:text-workspace-accent"
          >
            {copied ? 'Copied' : <Copy size={13} />}
          </button>
        </div>
      </div>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-3xl space-y-4 p-4">
          {/* Breadcrumb */}
          <div className="flex items-center gap-1 text-sm">
            <button
              onClick={() => {
                setPath('');
                setFile(null);
              }}
              className="font-medium text-workspace-accent hover:underline"
            >
              {repo}
            </button>
            {crumbs.map((c, i) => (
              <span key={i} className="flex items-center gap-1">
                <ChevronRight size={13} className="text-muted-foreground" />
                <button
                  onClick={() => {
                    setPath(crumbs.slice(0, i + 1).join('/'));
                    setFile(null);
                  }}
                  className="hover:underline"
                >
                  {c}
                </button>
              </span>
            ))}
            {file && (
              <span className="flex items-center gap-1">
                <ChevronRight size={13} className="text-muted-foreground" />
                <span className="font-medium">{file.name}</span>
              </span>
            )}
          </div>

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 size={16} className="animate-spin" />
              Loading…
            </div>
          ) : file ? (
            <div className="overflow-hidden rounded-lg border border-border/60">
              <div className="border-b border-border/50 bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground">
                {file.name} · {file.size} bytes
              </div>
              {file.is_binary || file.text === null ? (
                <p className="p-4 text-xs text-muted-foreground">Binary file not shown.</p>
              ) : /\.md$/i.test(file.name) ? (
                <div className="markdown-body p-4 text-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{file.text}</ReactMarkdown>
                </div>
              ) : (
                <div className="overflow-auto bg-muted/10 font-mono text-[12px] leading-[1.5]">
                  {file.text.split('\n').map((line, i) => (
                    <div key={i} className="flex hover:bg-workspace-accent-5">
                      <span className="w-12 flex-shrink-0 select-none border-r border-border/40 px-2 text-right text-muted-foreground/50">
                        {i + 1}
                      </span>
                      <code className="whitespace-pre px-3">{line || ' '}</code>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <>
              <div className="overflow-hidden rounded-lg border border-border/60">
                {latest && (
                  <div className="flex items-center gap-2 border-b border-border/50 bg-muted/30 px-3 py-1.5 text-xs">
                    <span className="font-medium text-foreground">{latest.author}</span>
                    <span className="truncate text-muted-foreground">{latest.message}</span>
                    <Link
                      href={`${codeBase}/r/${repoId}/commits?ref=${encodeURIComponent(ref)}`}
                      className="ml-auto flex flex-shrink-0 items-center gap-1 text-muted-foreground hover:text-workspace-accent"
                    >
                      <History size={12} />
                      <span className="font-mono">{latest.sha.slice(0, 7)}</span>
                      <span>· {timeAgo(latest.date)}</span>
                    </Link>
                  </div>
                )}
                <ul>
                  {entries.length === 0 && (
                  <li className="px-3 py-3 text-xs text-muted-foreground">Empty directory.</li>
                )}
                {entries.map((e) => (
                  <li key={e.path} className="border-b border-border/30 last:border-0">
                    <button
                      onClick={() => {
                        if (e.type === 'dir') {
                          setPath(e.path);
                          setFile(null);
                        } else {
                          void openFile(e);
                        }
                      }}
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-workspace-accent-5"
                    >
                      {e.type === 'dir' ? (
                        <Folder size={14} className="text-workspace-accent" />
                      ) : (
                        <FileIcon size={14} className="text-muted-foreground" />
                      )}
                      <span className="truncate">{e.name}</span>
                    </button>
                  </li>
                ))}
                </ul>
              </div>

              {readme !== null && (
                <div className="overflow-hidden rounded-lg border border-border/60">
                  <div className="border-b border-border/50 bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
                    README.md
                  </div>
                  <div className="markdown-body p-4 text-sm">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{readme}</ReactMarkdown>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
