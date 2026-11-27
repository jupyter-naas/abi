'use client';

/**
 * The parts of an instance's page under Features (an agent, a skill, a feed, a layer, a topic) that
 * every such form shares, as the General pages: its Save at the top right, faded until something
 * changes, and the "Unsaved changes / Discard changes" bar under the header. The edits themselves
 * are the page's, kept with `usePageDraft`.
 */
import { Save } from 'lucide-react';
import { SettingsBackButton } from '@/components/settings/settings-ui';
// The unsaved-changes bar of the General pages, and their Save button.
import '@/app/organizations/[orgId]/settings/general/general.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import { usePolicyHref } from '@/components/settings/use-policy-href';

/** Save (or Create): faded until `dirty`, "Saved!" a moment after. */
export function FormSaveButton({
  dirty,
  saving,
  saved = false,
  onSave,
  label = 'Save changes',
  action = 'save',
  disabled = false,
}: {
  dirty: boolean;
  saving: boolean;
  saved?: boolean;
  onSave: () => void;
  label?: string;
  /** `data-action`: `save`, `create`. */
  action?: string;
  /** Beyond `dirty`: a form that cannot be sent yet (a required field left empty), or read-only. */
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onSave}
      disabled={!dirty || saving || disabled}
      data-action={action}
      className={saved ? 'org-settings-primary-button org-settings-primary-button-saved' : 'org-settings-primary-button'}
    >
      <Save size={16} />
      {saved ? 'Saved!' : saving ? 'Saving...' : label}
    </button>
  );
}

/** Under the header while the form holds edits: says so (and what changed elsewhere meanwhile). */
export function UnsavedBar({
  show,
  conflicts = [],
  onDiscard,
  disabled = false,
}: {
  show: boolean;
  /** The fields changed elsewhere since the edit began: saving keeps the user's version. */
  conflicts?: string[];
  onDiscard: () => void;
  disabled?: boolean;
}) {
  if (!show) return null;
  return (
    <div className="org-settings-general-draft" role="status" data-unsaved-bar="">
      <p className="org-settings-general-draft-text">
        {conflicts.length > 0
          ? `Changed elsewhere since you began editing: ${conflicts.join(', ')}. Saving keeps your version.`
          : 'Unsaved changes.'}
      </p>
      <button type="button" onClick={onDiscard} disabled={disabled} className="org-settings-general-draft-discard" data-action="discard">
        Discard changes
      </button>
    </div>
  );
}

/** Back to the list an instance's page was opened from, above its header. */
export function InstanceBack({ href, label }: { href: string; label: string }) {
  // Back keeps the policy picked in the column (`?policy=`).
  const policyHref = usePolicyHref();
  return (
    <div className="-mb-2">
      <SettingsBackButton href={policyHref(href)} label={label} />
    </div>
  );
}
