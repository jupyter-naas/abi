'use client';

import { FileCode, FolderPlus, Upload, X } from 'lucide-react';
import './files-components.css';

type FilesAddSheetProps = {
  open: boolean;
  onClose: () => void;
  onNewFile: () => void;
  onNewFolder: () => void;
  onUpload: () => void;
};

export function FilesAddSheet({
  open,
  onClose,
  onNewFile,
  onNewFolder,
  onUpload,
}: FilesAddSheetProps) {
  if (!open) return null;

  return (
    <>
      <button
        type="button"
        className="files-add-sheet-backdrop"
        aria-label="Close add menu"
        onClick={onClose}
      />
      <div className="files-add-sheet-panel" role="dialog" aria-modal="true" aria-label="Add">
        <div className="files-add-sheet-header">
          <h2>Add</h2>
          <button type="button" onClick={onClose} className="files-add-sheet-close" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="files-add-sheet-actions">
          <button
            type="button"
            onClick={() => {
              onClose();
              onNewFile();
            }}
          >
            <FileCode size={20} />
            New file
          </button>
          <button
            type="button"
            onClick={() => {
              onClose();
              onNewFolder();
            }}
          >
            <FolderPlus size={20} />
            New folder
          </button>
          <button
            type="button"
            onClick={() => {
              onClose();
              onUpload();
            }}
          >
            <Upload size={20} />
            Upload files
          </button>
        </div>
      </div>
    </>
  );
}
