'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ModalBackdrop } from '@/components/ui/dialogs';
import { OTHERS_GROUP } from '@/lib/workspace-picker';

/** Properties a bulk edit can set. Only the group for now. */
const BULK_PROPERTIES = [{ id: 'workspace_group', label: 'Group' }] as const;
type BulkProperty = (typeof BULK_PROPERTIES)[number]['id'];

const GROUP_MAX_LENGTH = 100;

/**
 * Bulk edit (Organization Settings > Workspaces): pick a property, type its
 * new value, then confirm a warning before it is applied to every selected
 * workspace.
 */
export function BulkEditModal({
  open,
  count,
  groups,
  onClose,
  onApply,
}: {
  open: boolean;
  /** Number of selected workspaces. */
  count: number;
  /** Existing groups, suggested while typing. */
  groups: string[];
  onClose: () => void;
  /** Resolves when saved; rejects with the message to show. */
  onApply: (property: BulkProperty, value: string) => Promise<void>;
}) {
  const [property, setProperty] = useState<BulkProperty>('workspace_group');
  const [value, setValue] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setProperty('workspace_group');
    setValue('');
    setConfirming(false);
    setSaving(false);
    setError('');
  }, [open]);

  const trimmed = value.trim();
  const label = BULK_PROPERTIES.find((p) => p.id === property)?.label ?? property;
  const plural = count === 1 ? 'workspace' : 'workspaces';

  const apply = async () => {
    setSaving(true);
    setError('');
    try {
      await onApply(property, trimmed);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : 'Failed to update workspaces');
      setConfirming(false);
      setSaving(false);
    }
  };

  return (
    <ModalBackdrop open={open} onClose={saving ? () => undefined : onClose}>
      <div className="border border-border bg-background p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-foreground">Edit {count} {plural}</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              The value replaces the current one on every selected workspace.
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            disabled={saving}
            aria-label="Close"
          >
            <X size={16} />
          </Button>
        </div>

        {confirming ? (
          <div className="mt-5 flex gap-3 border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-foreground">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-500" />
            <p>
              {trimmed ? (
                <>
                  Set {label.toLowerCase()} to <strong>{trimmed}</strong> on {count} {plural}?
                </>
              ) : (
                <>
                  Clear the {label.toLowerCase()} of {count} {plural}? They will list under{' '}
                  <strong>{OTHERS_GROUP}</strong>.
                </>
              )}{' '}
              This cannot be undone in one step.
            </p>
          </div>
        ) : (
          <div className="mt-5 space-y-4">
            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-muted-foreground">Property</span>
              <select
                value={property}
                onChange={(event) => setProperty(event.target.value as BulkProperty)}
                className="h-9 w-full border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                {BULK_PROPERTIES.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-muted-foreground">New {label.toLowerCase()}</span>
              <input
                type="text"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') setConfirming(true);
                }}
                list="bulk-edit-groups"
                maxLength={GROUP_MAX_LENGTH}
                placeholder={`${OTHERS_GROUP} when empty`}
                autoFocus
                className="h-9 w-full border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
              <datalist id="bulk-edit-groups">
                {groups.map((group) => (
                  <option key={group} value={group} />
                ))}
              </datalist>
            </label>
          </div>
        )}

        {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

        <div className="mt-6 flex justify-end gap-2">
          {confirming ? (
            <>
              <Button variant="ghost" onClick={() => setConfirming(false)} disabled={saving}>
                Back
              </Button>
              <Button onClick={() => void apply()} disabled={saving}>
                {saving ? 'Applying...' : `Confirm on ${count} ${plural}`}
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={() => setConfirming(true)} disabled={count === 0}>
                Validate
              </Button>
            </>
          )}
        </div>
      </div>
    </ModalBackdrop>
  );
}
