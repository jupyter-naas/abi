'use client';

import { Building2, Folder, HardDrive, Server, User, Users } from 'lucide-react';
import type { FileViewSource } from '../lib/drive-label';
import './files-components.css';

const VIEW_ICONS: Record<FileViewSource, typeof Folder> = {
  'my-files': User,
  'workspace-files': Users,
  'organization-files': Building2,
  'platform-files': HardDrive,
  'system-files': Server,
};

export function FileViewIcon({ source, size = 16, className }: { source: FileViewSource; size?: number; className?: string }) {
  const Icon = VIEW_ICONS[source] ?? Folder;
  return <Icon size={size} className={className} aria-hidden />;
}

/**
 * All Views: one folder per view the caller may open; each opens into its view.
 */
export function FilesViewsRoot({
  folders,
  loading,
  onOpen,
}: {
  folders: readonly { source: FileViewSource; label: string }[];
  loading: boolean;
  onOpen: (source: FileViewSource) => void;
}) {
  if (folders.length === 0) {
    return (
      <p className="files-views-root-empty" role="status">
        {loading ? 'Loading…' : 'No view of the files is open to you here.'}
      </p>
    );
  }
  return (
    <ul className="files-views-root" aria-label="All Views" data-testid="files-views-root">
      {folders.map((folder) => (
        <li key={folder.source}>
          <button
            type="button"
            className="files-views-root-item"
            onClick={() => onOpen(folder.source)}
            data-testid="files-view-folder"
          >
            <Folder size={18} className="files-views-root-folder" aria-hidden />
            <FileViewIcon source={folder.source} size={14} className="files-views-root-icon" />
            <span className="files-views-root-label">{folder.label}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
