'use client';

import type { FileView } from '@/lib/file-views';
import {
  FILES_DRIVES,
  filesDriveFrom,
  filesSourceFrom,
  viewChoices,
  type FilesDrive,
  type FilesSource,
} from '../lib/drive-label';
import './files-components.css';

export type FilesViewPickerProps = {
  /** The views the caller may open (`GET /api/files/views`). */
  views: readonly FileView[];
  drive: FilesDrive;
  /** The View dropdown's choice: All Views or one view. */
  view: FilesSource;
  onDriveChange: (drive: FilesDrive) => void;
  onViewChange: (view: FilesSource) => void;
  /** The sidebar's denser layout. */
  compact?: boolean;
};

/**
 * The Drive and View dropdowns of the Files page and sidebar:
 * `[All Drives ▾] [All Views ▾]`. The View dropdown lists All Views, then only the
 * views the caller may open.
 */
export function FilesViewPicker({
  views,
  drive,
  view,
  onDriveChange,
  onViewChange,
  compact = false,
}: FilesViewPickerProps) {
  const choices = viewChoices(views, drive);
  // A view not (or no longer) listed reads as All Views until the caller picks one.
  const value = choices.some((choice) => choice.value === view) ? view : 'all';
  return (
    <div className={compact ? 'files-view-picker is-compact' : 'files-view-picker'} data-testid="files-view-picker">
      <select
        className="files-view-picker-select"
        aria-label="Drive"
        value={drive}
        onChange={(event) => onDriveChange(filesDriveFrom(event.target.value))}
        data-testid="files-drive-select"
      >
        {FILES_DRIVES.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <select
        className="files-view-picker-select"
        aria-label="View"
        value={value}
        onChange={(event) => onViewChange(filesSourceFrom(event.target.value) ?? 'all')}
        data-testid="files-view-select"
      >
        {choices.map((choice) => (
          <option key={choice.value} value={choice.value}>
            {choice.label}
          </option>
        ))}
      </select>
    </div>
  );
}
