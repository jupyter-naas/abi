'use client';

import './source-control.css';

import { BookMarked, Building2, GitBranch, Globe, Lock } from 'lucide-react';
import { detectLanguage, formatBytes } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Badge, RelativeTime } from '../data-ui';
import { fileIcon } from './object-storage';
import { MarkdownView } from './source-control-markdown';
import type { ServiceView } from './types';

function depthOf(entry: ResourceEntry): number {
  return entry.id.split('/').length;
}

function isRepository(entry: ResourceEntry): boolean {
  return entry.kind === 'container' && depthOf(entry) === 2;
}

function pathInRepo(id: string): string {
  return id.split('/').slice(2).join('/');
}

function extension(name: string): string {
  return name.includes('.') ? (name.split('.').pop() ?? '').toUpperCase() : '';
}

function RepositoryBadges({ entry }: { entry: ResourceEntry }) {
  const a = entry.attributes;
  return (
    <>
      {a.visibility === 'public' ? (
        <Badge tone="info">
          <Globe size={11} aria-hidden="true" /> public
        </Badge>
      ) : (
        <Badge>
          <Lock size={11} aria-hidden="true" /> private
        </Badge>
      )}
      {a.default_branch && (
        <Badge mono>
          <GitBranch size={11} aria-hidden="true" /> {a.default_branch}
        </Badge>
      )}
      {a.empty === 'yes' && <Badge tone="warn">empty</Badge>}
    </>
  );
}

/** Rendered Markdown for README-like files; ``null`` lets the generic preview show code. */
function markdownPreview(detail: ResourceDetail) {
  const content = detail.content;
  if (!content || content.encoding !== 'text') return null;
  if (!/\.(md|markdown)$/i.test(detail.entry.name)) return null;
  return <MarkdownView text={content.text ?? ''} />;
}

export const sourceControlView: ServiceView = {
  name: 'source_control',
  label: 'Source control',
  description: 'Repositories on the platform forge and the files on their default branch.',
  icon: GitBranch,
  group: 'Platform',
  noun: { one: 'file', many: 'files' },
  entryIcon: (entry) => {
    const depth = depthOf(entry);
    if (depth === 1) return Building2;
    if (depth === 2 && entry.kind === 'container') return BookMarked;
    return fileIcon(entry);
  },
  nounFor: (entry) => {
    const depth = depthOf(entry);
    if (depth === 1) return { one: 'owner', many: 'owners' };
    if (isRepository(entry)) return { one: 'repository', many: 'repositories' };
    return entry.kind === 'container' ? { one: 'folder', many: 'folders' } : { one: 'file', many: 'files' };
  },
  canCreate: (depth) => (depth >= 2 ? true : 'Open a repository to add files to it.'),
  level: (depth) => {
    if (depth === 0) {
      return {
        noun: { one: 'owner', many: 'owners' },
        layout: 'cards',
        columns: [
          {
            id: 'repositories',
            label: 'Repositories',
            width: '1fr',
            render: (e) => <span className="data-num">{e.attributes.repositories ?? '—'}</span>,
          },
        ],
        emptyTitle: 'No repository on the forge',
        emptyText: 'Repositories appear here once modules or users create them on the platform forge.',
      };
    }
    if (depth === 1) {
      return {
        noun: { one: 'repository', many: 'repositories' },
        layout: 'cards',
        card: (entry) =>
          entry.attributes.description ? (
            <p className="data-scm-description">{entry.attributes.description}</p>
          ) : (
            <p className="data-scm-description data-muted">No description</p>
          ),
        columns: [{ id: 'updated', label: 'Updated', width: '1fr', render: (e) => <RelativeTime iso={e.modified} /> }],
        emptyTitle: 'No repository',
        emptyText: 'This owner has no repository left.',
      };
    }
    return {
      noun: { one: 'item', many: 'items' },
      columns: [
        {
          id: 'kind',
          label: 'Kind',
          width: '80px',
          render: (e) => <span className="data-muted">{e.kind === 'container' ? 'Folder' : extension(e.name) || 'File'}</span>,
        },
        {
          id: 'size',
          label: 'Size',
          width: '88px',
          align: 'end',
          render: (e) => <span className="data-num">{e.kind === 'item' ? formatBytes(e.size) : ''}</span>,
        },
      ],
      emptyTitle: 'This folder is empty',
      emptyText: 'Create a file or drop files here: each one is committed to the default branch.',
    };
  },
  badges: (entry) => (isRepository(entry) ? <RepositoryBadges entry={entry} /> : null),
  facts: (detail) => [
    { label: 'Repository', value: <span className="data-mono">{detail.entry.id.split('/').slice(0, 2).join('/')}</span> },
    { label: 'Path', value: <span className="data-mono">{pathInRepo(detail.entry.id)}</span> },
    { label: 'Size', value: formatBytes(detail.entry.size) },
  ],
  preview: (detail) => markdownPreview(detail),
  createLabel: 'New file',
  acceptsDrops: true,
  editor: {
    language: (id) => detectLanguage(id),
    namePlaceholder: 'docs/notes.md',
    allowUpload: true,
    validateName: (name) =>
      /(^\/)|(\/$)|(^|\/)\.\.?(\/|$)|\\/.test(name.trim()) ? 'Use a relative path like docs/notes.md.' : null,
  },
  deleteWarning: (entry) =>
    isRepository(entry)
      ? 'This deletes the repository and its whole history on the forge. Existing clones keep their copy.'
      : "This commits the file's removal on the default branch. Earlier versions stay in the repository history.",
};
