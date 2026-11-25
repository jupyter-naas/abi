'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { Input, Select } from '@/components/ui/input';
import { Notice } from '@/components/ui/notice';
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
    <Dialog
      open={open}
      title={`Edit ${count} ${plural}`}
      description="The value replaces the current one on every selected workspace."
      dismissible={!saving}
      onClose={onClose}
      footer={
        confirming ? (
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
        )
      }
    >
      {confirming ? (
        <Notice tone="warning" icon={<AlertTriangle size={16} />}>
          {trimmed ? (
            <>
              Set {label.toLowerCase()} to <strong>{trimmed}</strong> on {count} {plural}?
            </>
          ) : (
            <>
              Clear the {label.toLowerCase()} of {count} {plural}? They will list under <strong>{OTHERS_GROUP}</strong>.
            </>
          )}{' '}
          This cannot be undone in one step.
        </Notice>
      ) : (
        <>
          <Field label="Property" htmlFor="bulk-edit-property">
            <Select
              id="bulk-edit-property"
              value={property}
              onChange={(event) => setProperty(event.target.value as BulkProperty)}
            >
              {BULK_PROPERTIES.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={`New ${label.toLowerCase()}`} htmlFor="bulk-edit-value">
            <Input
              id="bulk-edit-value"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') setConfirming(true);
              }}
              list="bulk-edit-groups"
              maxLength={GROUP_MAX_LENGTH}
              placeholder={`${OTHERS_GROUP} when empty`}
              data-autofocus
            />
            <datalist id="bulk-edit-groups">
              {groups.map((group) => (
                <option key={group} value={group} />
              ))}
            </datalist>
          </Field>
        </>
      )}
      {error && <Notice tone="error">{error}</Notice>}
    </Dialog>
  );
}
