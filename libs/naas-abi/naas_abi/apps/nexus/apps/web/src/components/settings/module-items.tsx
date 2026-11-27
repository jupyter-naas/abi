'use client';

/**
 * The Enabled column of the pages under Features that list module items (Agents, Apps,
 * Workflows), its batch bar and what a save said: a table of switches, each change saved at once
 * into the policy picked in the Settings column, the rows selected enabled or disabled together,
 * asked first. The items come from `useModuleItems`.
 */
import type { MouseEvent } from 'react';
import { AlertCircle } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { Notice } from '@/components/ui/notice';
import { BulkBar, onOffActions, type RowSelection } from '@/components/settings/bulk-access';
import { moduleItemKey, type ModuleItem } from './module-items-model';
import type { ModuleItems } from './use-module-items';

/** The batch actions: enable the items selected, or disable them. */
export const ENABLE_ACTIONS = onOffActions({ on: 'Enable', off: 'Disable' }, (on) =>
  on
    ? 'They are enabled in one save.'
    : 'They are disabled in one save; a module enabled whole goes item by item, its other items kept.'
);

const stop = (event: MouseEvent) => event.stopPropagation();

/** What a save did, why it failed, and whether the policy may change here. */
export function ModuleItemsStatus({ state }: { state: ModuleItems }) {
  const edited = state.offer?.policy ?? state.offer?.access_policy ?? null;
  return (
    <>
      {state.error && (
        <Notice tone="error" icon={<AlertCircle size={14} />}>
          {state.error}
        </Notice>
      )}
      {state.notice && (
        <p className="text-xs text-muted-foreground" role="status" data-module-items-notice="">
          {state.notice}
        </p>
      )}
      {state.offer && !state.editable && (
        <Notice tone="info">
          {edited
            ? `Read-only: IAM does not let you change ${edited.name}.`
            : 'This workspace has no access policy yet.'}
        </Notice>
      )}
    </>
  );
}

/**
 * A row's Enabled cell: its item's checkbox, saved at once. What the workspace builds itself
 * (`builtHere`) is always enabled, without one; a row no module item answers to is usable, and
 * cannot be changed here.
 */
export function EnabledCell({
  state,
  item,
  label,
  builtHere = false,
}: {
  state: ModuleItems;
  item: ModuleItem | null;
  /** The row's name, as the notice says it. */
  label: string;
  builtHere?: boolean;
}) {
  if (builtHere) {
    return (
      <td data-field="enabled" onClick={stop}>
        <span className="text-xs text-muted-foreground" data-enabled-always="">
          Always enabled
        </span>
      </td>
    );
  }
  if (!item) {
    return (
      <td data-field="enabled" onClick={stop}>
        {state.ready ? (
          <Checkbox
            checked
            disabled
            aria-label={`${label} is enabled`}
            title="Not among the module items this policy sets"
            data-enabled=""
          />
        ) : null}
      </td>
    );
  }
  return (
    <td data-field="enabled" onClick={stop}>
      <Checkbox
        checked={item.offered}
        // Enabling needs the right to give its module here.
        disabled={!state.editable || state.saving || (!item.grantable && !item.offered)}
        aria-label={`Enable ${label}`}
        data-enabled={moduleItemKey(item)}
        onCheckedChange={(on) => void state.setEnabled([item], on, () => `${label} ${on ? 'enabled' : 'disabled'}.`)}
      />
    </td>
  );
}

/** The batch bar: enable or disable the items selected (`moduleItemKey`s), in one save. */
export function EnableBulkBar({
  state,
  selection,
  noun,
  plural = `${noun}s`,
}: {
  state: ModuleItems;
  selection: RowSelection;
  noun: string;
  plural?: string;
}) {
  const targets = () =>
    [...selection.selected].map((key) => state.byKey.get(key)).filter((item): item is ModuleItem => !!item);
  return (
    <BulkBar
      selection={selection}
      noun={noun}
      plural={plural}
      actions={ENABLE_ACTIONS}
      onApply={(id) => {
        const on = id === 'on';
        return state.setEnabled(targets(), on, (count) => `${count} ${count === 1 ? noun : plural} ${on ? 'enabled' : 'disabled'}.`);
      }}
      // Enabling an item needs the right to give its module here.
      skippedFor={(id) => (id === 'on' ? targets().filter((item) => !item.offered && !item.grantable).length : 0)}
      change="this change"
      disabled={!state.editable || state.saving}
    />
  );
}
