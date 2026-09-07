'use client';

import type { FileInfo } from '@/stores/files';
import './files-components.css';

type FilesMobileRowProps = {
  file: FileInfo;
  isDropTarget: boolean;
  icon: React.ReactNode;
  sizeLabel: string;
  dateLabel: string;
  onOpen: () => void;
  onDragStart?: (e: React.DragEvent) => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDragLeave?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
  actions: React.ReactNode;
};

export function FilesMobileRow({
  file,
  isDropTarget,
  icon,
  sizeLabel,
  dateLabel,
  onOpen,
  onDragStart,
  onDragOver,
  onDragLeave,
  onDrop,
  actions,
}: FilesMobileRowProps) {
  return (
    <li
      draggable={!!onDragStart}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={`files-mobile-row${isDropTarget ? ' is-drop-target' : ''}`}
    >
      <button type="button" onClick={onOpen} className="files-mobile-row-main">
        <span className="files-mobile-row-icon">{icon}</span>
        <span className="files-mobile-row-text">
          <span className="files-mobile-row-name">{file.name}</span>
          {file.type === 'file' && (
            <span className="files-mobile-row-meta">
              {sizeLabel} · {dateLabel}
            </span>
          )}
        </span>
      </button>
      <div className="files-mobile-row-actions">{actions}</div>
    </li>
  );
}
