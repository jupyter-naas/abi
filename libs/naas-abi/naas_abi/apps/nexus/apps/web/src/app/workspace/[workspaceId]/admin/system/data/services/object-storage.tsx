'use client';

import {
  File,
  FileArchive,
  FileCode,
  FileImage,
  FileJson,
  FileSpreadsheet,
  FileText,
  Folder,
  HardDrive,
  type LucideIcon,
} from 'lucide-react';
import { detectLanguage, formatBytes, isImage } from '../data-model';
import type { ResourceEntry } from '../data-types';
import { RelativeTime } from '../data-ui';
import type { ServiceView } from './types';

const CODE = /\.(py|ts|tsx|js|jsx|mjs|go|rs|java|sh|sql|yaml|yml|toml|ini|html|css|xml)$/i;

export function fileIcon(entry: ResourceEntry): LucideIcon {
  if (entry.kind === 'container') return Folder;
  const name = entry.name.toLowerCase();
  const type = entry.attributes.media_type ?? '';
  if (isImage(name, type)) return FileImage;
  if (name.endsWith('.json') || name.endsWith('.jsonl') || type.includes('json')) return FileJson;
  if (/\.(csv|tsv|xlsx?|parquet)$/.test(name)) return FileSpreadsheet;
  if (/\.(zip|gz|tgz|tar|bz2|7z)$/.test(name)) return FileArchive;
  if (CODE.test(name)) return FileCode;
  if (/\.(md|txt|log|ttl|nt|rdf|pdf|docx?)$/.test(name) || type.startsWith('text/')) return FileText;
  return File;
}

function kindLabel(entry: ResourceEntry): string {
  if (entry.kind === 'container') return 'Folder';
  const ext = entry.name.includes('.') ? entry.name.split('.').pop() : '';
  return ext ? ext.toUpperCase() : (entry.attributes.media_type ?? 'File');
}

export const objectStorageView: ServiceView = {
  name: 'object_storage',
  label: 'Object storage',
  description: 'Files and blobs written by modules, Nexus files and uploads.',
  icon: HardDrive,
  group: 'Storage',
  noun: { one: 'file', many: 'files' },
  entryIcon: fileIcon,
  nounFor: (entry) => (entry.kind === 'container' ? { one: 'folder', many: 'folders' } : { one: 'file', many: 'files' }),
  level: () => ({
    noun: { one: 'item', many: 'items' },
    columns: [
      { id: 'kind', label: 'Kind', width: '88px', render: (e) => <span className="data-muted">{kindLabel(e)}</span> },
      {
        id: 'size',
        label: 'Size',
        width: '88px',
        align: 'end',
        render: (e) => <span className="data-num">{e.kind === 'item' ? formatBytes(e.size) : ''}</span>,
      },
      { id: 'modified', label: 'Modified', width: '120px', render: (e) => <RelativeTime iso={e.modified} /> },
    ],
    emptyTitle: 'This folder is empty',
    emptyText: 'Drop files here to upload them, or create a file.',
  }),
  facts: (detail) => [
    { label: 'Size', value: formatBytes(detail.entry.size) },
    { label: 'Type', value: detail.entry.attributes.media_type ?? kindLabel(detail.entry) },
    { label: 'Modified', value: <RelativeTime iso={detail.entry.modified} /> },
  ],
  createLabel: 'New file',
  acceptsDrops: true,
  editor: {
    language: (id) => detectLanguage(id),
    namePlaceholder: 'notes.md',
    allowUpload: true,
  },
  deleteWarning: () => 'The object is removed from storage. Anything reading it gets "not found" afterwards.',
};
