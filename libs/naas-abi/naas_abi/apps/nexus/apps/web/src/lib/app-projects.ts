/**
 * App projects: static apps created or copied in Nexus and edited in the
 * Apps editor (code | live preview | Apps agent).
 *
 * API: /api/app-projects (see services/apps/projects in the API). The preview
 * loads from the API origin under /app-preview/<token>/ in a sandboxed,
 * opaque origin: the app's code never shares the Nexus session.
 */
import { authFetch } from '@/stores/auth';

export type AppProjectFile = { path: string; size: number };

export type AppProjectOrigin = {
  app_id: string;
  module_path: string;
  app_name: string;
  repo_path: string | null;
  source_commit: string | null;
  kind: 'bundled' | 'external' | string;
  url: string | null;
};

export type AppProjectSubmission = {
  branch: string;
  url: string | null;
  commit_sha: string | null;
  pull_request_url: string | null;
  target_path: string;
  submitted_at: string | null;
};

export type AppProject = {
  slug: string;
  title: string;
  description: string;
  icon_emoji: string;
  workspace_id: string;
  repo_id: string;
  branch: string;
  root: string;
  entry: string | null;
  dirty: boolean;
  commit_sha: string | null;
  updated_at: string | null;
  archived: boolean;
  origin: AppProjectOrigin | null;
  submission: AppProjectSubmission | null;
  files: AppProjectFile[];
};

export type AppProjectCommit = { sha: string; message: string; author: string; date: string | null };
export type AppProjectIssue = { level: 'error' | 'warning' | 'info'; message: string; path: string | null };
export type AppSubmitConfig = {
  configured: boolean;
  repo: string | null;
  base_branch: string | null;
  modules: string[];
  default_module: string | null;
};

/** Must match APP_PROJECT_WRITE_TOOLS in naas_abi/agents/tools/app_builder_tools.py. */
export const APP_PROJECT_WRITE_TOOLS = [
  'create_app_project',
  'edit_module_app',
  'write_app_file',
  'replace_in_app_file',
  'delete_app_file',
  'save_app_project',
  'submit_app_project',
] as const;

export const APP_PREVIEW_MESSAGE_SOURCE = 'nexus-app-preview';

export function isAppProjectWriteTool(rawName: string | null | undefined): boolean {
  const name = (rawName || '').toLowerCase().split(/[.:/\s]+/).filter(Boolean).pop() || '';
  return (APP_PROJECT_WRITE_TOOLS as readonly string[]).includes(name);
}

export function appEditorPath(workspaceId: string, slug: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/apps/p/${encodeURIComponent(slug)}`;
}

export function previewUrl(apiBase: string, previewPath: string, file?: string): string {
  const base = `${apiBase.replace(/\/+$/, '')}${previewPath}`;
  if (!file) return base;
  return `${base}${file.split('/').map(encodeURIComponent).join('/')}`;
}

/** Error text from the preview bridge's postMessage, else null. */
export function previewErrorFromMessage(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null;
  const msg = data as { source?: unknown; type?: unknown; message?: unknown };
  if (msg.source !== APP_PREVIEW_MESSAGE_SOURCE || msg.type !== 'error') return null;
  return typeof msg.message === 'string' ? msg.message : null;
}

export type FileTreeNode = {
  name: string;
  path: string;
  size?: number;
  children?: FileTreeNode[];
};

export function buildFileTree(files: AppProjectFile[]): FileTreeNode[] {
  const root: FileTreeNode = { name: '', path: '', children: [] };
  for (const file of files) {
    const parts = file.path.split('/');
    let node = root;
    parts.forEach((part, index) => {
      const path = parts.slice(0, index + 1).join('/');
      const isFile = index === parts.length - 1;
      node.children = node.children || [];
      let child = node.children.find((c) => c.name === part && Boolean(c.children) !== isFile);
      if (!child) {
        child = isFile ? { name: part, path, size: file.size } : { name: part, path, children: [] };
        node.children.push(child);
      }
      node = child;
    });
  }
  const sort = (nodes: FileTreeNode[]): FileTreeNode[] =>
    nodes
      .map((n) => (n.children ? { ...n, children: sort(n.children) } : n))
      .sort((a, b) => {
        if (Boolean(a.children) !== Boolean(b.children)) return a.children ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
  return sort(root.children || []);
}

const LANGUAGES: Record<string, string> = {
  html: 'html',
  htm: 'html',
  css: 'css',
  js: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  ts: 'typescript',
  json: 'json',
  webmanifest: 'json',
  md: 'markdown',
  svg: 'xml',
  xml: 'xml',
  toml: 'ini',
  yaml: 'yaml',
  yml: 'yaml',
  py: 'python',
  csv: 'plaintext',
  txt: 'plaintext',
};

export function languageForPath(path: string): string {
  const name = path.split('/').pop() || '';
  const ext = name.includes('.') ? name.split('.').pop()!.toLowerCase() : '';
  return LANGUAGES[ext] || 'plaintext';
}

// -- API ------------------------------------------------------------------------

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    cache: 'no-store',
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    const detail = typeof body.detail === 'string' ? body.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

const q = (params: Record<string, string>) => new URLSearchParams(params).toString();
const base = (slug?: string) =>
  `/api/app-projects/${slug ? `${encodeURIComponent(slug)}` : ''}`;

export const appProjectsApi = {
  list: (workspaceId: string) => call<AppProject[]>(`${base()}?${q({ workspace_id: workspaceId })}`),
  create: (workspaceId: string, title: string, description = '') =>
    call<AppProject>(base(), {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId, title, description }),
    }),
  importModuleApp: (workspaceId: string, appId: string) =>
    call<AppProject>(`${base()}import`, {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId, app_id: appId }),
    }),
  get: (workspaceId: string, slug: string) =>
    call<AppProject>(`${base(slug)}?${q({ workspace_id: workspaceId })}`),
  rename: (workspaceId: string, slug: string, title: string) =>
    call<AppProject>(base(slug), {
      method: 'PATCH',
      body: JSON.stringify({ workspace_id: workspaceId, title }),
    }),
  readFile: (workspaceId: string, slug: string, path: string) =>
    call<{ path: string; size: number; content: string | null; binary: boolean }>(
      `${base(slug)}/file?${q({ workspace_id: workspaceId, path })}`,
    ),
  writeFile: (workspaceId: string, slug: string, path: string, content: string) =>
    call<AppProjectFile>(`${base(slug)}/file`, {
      method: 'PUT',
      body: JSON.stringify({ workspace_id: workspaceId, path, content }),
    }),
  deleteFile: (workspaceId: string, slug: string, path: string) =>
    call<{ deleted: boolean }>(`${base(slug)}/file?${q({ workspace_id: workspaceId, path })}`, {
      method: 'DELETE',
    }),
  save: (workspaceId: string, slug: string, message?: string) =>
    call<{ saved: boolean; commit: AppProjectCommit | null }>(`${base(slug)}/save`, {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId, message: message || null }),
    }),
  discard: (workspaceId: string, slug: string) =>
    call<AppProject>(`${base(slug)}/discard`, {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId }),
    }),
  history: (workspaceId: string, slug: string) =>
    call<AppProjectCommit[]>(`${base(slug)}/history?${q({ workspace_id: workspaceId })}`),
  check: (workspaceId: string, slug: string) =>
    call<AppProjectIssue[]>(`${base(slug)}/check?${q({ workspace_id: workspaceId })}`),
  previewToken: (workspaceId: string, slug: string) =>
    call<{ path: string; expires_in: number }>(`${base(slug)}/preview-token`, {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId }),
    }),
  submitConfig: () => call<AppSubmitConfig>(`${base()}submit-config`),
  submit: (workspaceId: string, slug: string, module?: string) =>
    call<AppProjectSubmission>(`${base(slug)}/submit`, {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId, module: module || null }),
    }),
};
