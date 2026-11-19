'use client';

import { OntologyMultiPicker } from '@/components/shell/sidebar/ontology-multi-picker';
import type { FileView } from '@/lib/file-views';
import {
  FILES_DRIVES,
  filesDriveFrom,
  filesSourceFrom,
  viewChoices,
  type FilesDrive,
  type FilesSource,
} from '../lib/drive-label';

export type FilesViewPickerProps = {
  /** The views the caller may open (`GET /api/files/views`). */
  views: readonly FileView[];
  drive: FilesDrive;
  /** The View picker's choice: All Views or one view. */
  view: FilesSource;
  onDriveChange: (drive: FilesDrive) => void;
  onViewChange: (view: FilesSource) => void;
};

const ALL_DRIVES = FILES_DRIVES[0];
const DRIVE_ITEMS = FILES_DRIVES.slice(1).map((option) => ({ value: option.value, label: option.label }));

/**
 * The Files sidebar's Drive and View pickers, the ontology sidebar's picker in its
 * single-choice mode, stacked: Drive above View. The View picker lists All Views,
 * then only the views the caller may open.
 */
export function FilesViewPicker({ views, drive, view, onDriveChange, onViewChange }: FilesViewPickerProps) {
  const [allViews, ...viewItems] = viewChoices(views, drive);
  // A view not (or no longer) listed reads as All Views until the caller picks one.
  const chosenView = viewItems.find((choice) => choice.value === view);
  const chosenDrive = DRIVE_ITEMS.find((option) => option.value === drive);
  return (
    <div className="ontology-sidebar-filters mb-1.5" data-testid="files-view-picker">
      <OntologyMultiPicker
        single
        ariaLabel="Choose drive"
        items={DRIVE_ITEMS}
        value={chosenDrive ? [chosenDrive.value] : []}
        onToggle={(value) => onDriveChange(filesDriveFrom(value))}
        onClear={() => onDriveChange(filesDriveFrom(ALL_DRIVES.value))}
        loading={false}
        error={null}
        label={chosenDrive?.label ?? ALL_DRIVES.label}
        allLabel={ALL_DRIVES.label}
        noun="drives"
      />
      <OntologyMultiPicker
        single
        ariaLabel="Choose view"
        items={viewItems.map((choice) => ({ value: choice.value, label: choice.label }))}
        value={chosenView ? [chosenView.value] : []}
        onToggle={(value) => onViewChange(filesSourceFrom(value) ?? allViews.value)}
        onClear={() => onViewChange(allViews.value)}
        loading={false}
        error={null}
        label={chosenView?.label ?? allViews.label}
        allLabel={allViews.label}
        noun="views"
      />
    </div>
  );
}
