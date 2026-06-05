'use client';

import { Loader2, Save } from 'lucide-react';

export function SaveNetworkViewDialog({
  name,
  viewType,
  existingViewTypes,
  visibility,
  saving,
  onNameChange,
  onViewTypeChange,
  onVisibilityChange,
  onSave,
  onCancel,
}: {
  name: string;
  viewType: string;
  existingViewTypes: string[];
  visibility: 'workspace' | 'personal';
  saving: boolean;
  onNameChange: (value: string) => void;
  onViewTypeChange: (value: string) => void;
  onVisibilityChange: (value: 'workspace' | 'personal') => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const typeSuggestions = Array.from(
    new Set(['Unknown', ...existingViewTypes.map((t) => t.trim()).filter(Boolean)])
  ).sort((a, b) => a.localeCompare(b));
  const typeListId = 'save-network-view-type-options';
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-96 rounded-lg border bg-background p-4 shadow-xl">
        <h3 className="mb-3 text-sm font-semibold">Save network view</h3>
        <div className="space-y-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Name</label>
            <input
              autoFocus
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="View name"
              className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && name.trim()) onSave();
                if (e.key === 'Escape') onCancel();
              }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Type</label>
            <input
              list={typeListId}
              value={viewType}
              onChange={(e) => onViewTypeChange(e.target.value)}
              placeholder="Unknown"
              className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
            <datalist id={typeListId}>
              {typeSuggestions.map((type) => (
                <option key={type} value={type} />
              ))}
            </datalist>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Visibility</label>
            <select
              value={visibility}
              onChange={(e) => onVisibilityChange(e.target.value as 'workspace' | 'personal')}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            >
              <option value="workspace">Workspace</option>
              <option value="personal" disabled>Personal (coming soon)</option>
            </select>
          </div>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Cancel
          </button>
          <button
            onClick={onSave}
            disabled={!name.trim() || saving}
            className="flex items-center gap-2 rounded-md bg-workspace-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
