'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Check,
  ChevronDown,
  ChevronRight,
  Code,
  Copy,
  File as FileIcon,
  Folder,
  GitBranch,
  History,
  KeyRound,
  Loader2,
  UploadCloud,
  X,
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
  const [error, setError] = useState<string | null>(null);
  // Clone dropdown + on-demand personal access token (private repos need auth).
  const [cloneOpen, setCloneOpen] = useState(false);
  const [isPrivate, setIsPrivate] = useState(true);
  const [gitToken, setGitToken] = useState<{ username: string; token: string } | null>(null);
  const [tokenBusy, setTokenBusy] = useState(false);
  const [tokenErr, setTokenErr] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState('');

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
            private: boolean;
          }>;
          const m = repos.find((r) => r.repo_id === repoId);
          if (m) {
            setCloneUrl(m.clone_url);
            setEmpty(m.empty);
            setIsPrivate(m.private);
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

  // Dismiss the clone dropdown with Escape.
  useEffect(() => {
    if (!cloneOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setCloneOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [cloneOpen]);

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
  // host needs TLS verification turned off for that one command. Match the host
  // only (not the whole URL) so a repo name containing "localhost" can't trip it.
  const insecureClone = (() => {
    try {
      const host = cloneUrl ? new URL(cloneUrl).hostname : '';
      return host === 'localhost' || host.endsWith('.localhost');
    } catch {
      return false;
    }
  })();
  const gitClone = (url: string) =>
    url ? `git clone ${insecureClone ? '-c http.sslVerify=false ' : ''}${url}` : '';
  // Once a token is minted, embed `username:token` after the URL's scheme so the
  // clone needs no interactive credential prompt (mirrors the Branches push panel).
  const authedUrl =
    gitToken && cloneUrl
      ? cloneUrl.replace(
          /^(https?:\/\/)/,
          `$1${encodeURIComponent(gitToken.username)}:${encodeURIComponent(gitToken.token)}@`,
        )
      : '';

  const copyField = async (key: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedKey(key);
      window.setTimeout(() => setCopiedKey(''), 1500);
    } catch {
      /* ignore */
    }
  };

  const generateToken = async () => {
    setTokenBusy(true);
    setTokenErr(null);
    try {
      const res = await authFetch('/api/coding-environments/git-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId, repo_id: repoId }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body?.detail || `Failed (${res.status})`);
      }
      setGitToken((await res.json()) as { username: string; token: string });
    } catch (e) {
      setTokenErr((e as Error).message);
    } finally {
      setTokenBusy(false);
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
        <div className="relative ml-auto">
          <button
            onClick={() => setCloneOpen((v) => !v)}
            className="flex items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1 text-xs font-medium text-white hover:opacity-90"
          >
            <Code size={13} />
            Clone
            <ChevronDown size={13} />
          </button>

          {cloneOpen && (
            <>
              {/* click-away backdrop */}
              <button
                aria-hidden
                tabIndex={-1}
                onClick={() => setCloneOpen(false)}
                className="fixed inset-0 z-10 cursor-default"
              />
              <div
                role="dialog"
                aria-modal="false"
                aria-label="Clone repository"
                className="absolute right-0 z-20 mt-1 w-[440px] space-y-3 rounded-lg border border-border bg-popover p-3 text-xs shadow-lg"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Clone over HTTPS</span>
                  <button
                    onClick={() => setCloneOpen(false)}
                    aria-label="Close"
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X size={14} />
                  </button>
                </div>

                <p className="text-muted-foreground">
                  {isPrivate ? (
                    <>
                      This is a private repository. When git asks for credentials, use your{' '}
                      <span className="font-medium text-foreground">username</span> below and a{' '}
                      <span className="font-medium text-foreground">personal access token</span> as
                      the password — not your login password.
                    </>
                  ) : (
                    <>This repository is public — clone it anonymously, no credentials needed.</>
                  )}
                </p>

                {/* Plain URL — works, but git will prompt for the credentials above. */}
                <div>
                  <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    Clone command
                  </div>
                  <div className="flex items-start gap-2 rounded-md border border-border bg-muted/30 p-2">
                    <code className="min-w-0 flex-1 break-all font-mono">{gitClone(cloneUrl)}</code>
                    <button
                      onClick={() => copyField('plain', gitClone(cloneUrl))}
                      title="Copy"
                      aria-label="Copy clone command"
                      className="flex-shrink-0 text-muted-foreground hover:text-workspace-accent"
                    >
                      {copiedKey === 'plain' ? <Check size={13} /> : <Copy size={13} />}
                    </button>
                  </div>
                </div>

                {isPrivate &&
                  (!gitToken ? (
                  <div className="space-y-2">
                    <button
                      onClick={generateToken}
                      disabled={tokenBusy}
                      className="flex w-full items-center justify-center gap-1.5 rounded-md border border-workspace-accent px-2.5 py-1.5 font-medium text-workspace-accent hover:bg-workspace-accent-10 disabled:opacity-50"
                    >
                      {tokenBusy ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : (
                        <KeyRound size={13} />
                      )}
                      Generate access token
                    </button>
                    <p className="text-muted-foreground">
                      Creates a personal access token and gives you a ready-to-paste command with
                      it embedded — no prompt. The token is shown only once.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div>
                      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-workspace-accent">
                        <KeyRound size={11} />
                        Ready to paste — token embedded
                      </div>
                      <div className="flex items-start gap-2 rounded-md border border-workspace-accent/40 bg-workspace-accent-5 p-2">
                        <code className="min-w-0 flex-1 break-all font-mono">
                          {gitClone(authedUrl)}
                        </code>
                        <button
                          onClick={() => copyField('authed', gitClone(authedUrl))}
                          title="Copy"
                          aria-label="Copy clone command with token"
                          className="flex-shrink-0 text-muted-foreground hover:text-workspace-accent"
                        >
                          {copiedKey === 'authed' ? <Check size={13} /> : <Copy size={13} />}
                        </button>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-muted-foreground">
                      <span>
                        username{' '}
                        <span className="font-mono text-foreground">{gitToken.username}</span>
                      </span>
                      <button
                        onClick={() => copyField('token', gitToken.token)}
                        title="Copy token"
                        aria-label="Copy access token"
                        className="inline-flex items-center gap-1 hover:text-workspace-accent"
                      >
                        token{' '}
                        <span className="font-mono text-foreground">
                          {gitToken.token.slice(0, 6)}…
                        </span>
                        {copiedKey === 'token' ? <Check size={12} /> : <Copy size={12} />}
                      </button>
                    </div>
                    <p className="text-amber-600 dark:text-amber-500">
                      Save this token now — it won’t be shown again.
                    </p>
                    <p className="text-muted-foreground">
                      This command stores the token in the clone’s{' '}
                      <code className="font-mono">.git/config</code> and your shell history — use it
                      on a trusted machine, or run the plain command above and paste the token when
                      prompted.
                    </p>
                  </div>
                ))}

                {tokenErr && <p className="text-red-600">{tokenErr}</p>}
              </div>
            </>
          )}
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
