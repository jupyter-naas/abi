'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { ownerHref } from '@/components/access/policies/policy-owners';
import { SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import { createFeatureAccessApi, type FeatureAccessApi } from './feature-access-api';
import {
  changesFrom,
  choicesOf,
  draftOf,
  otherPolicies,
  rowNotes,
  sortedRows,
  type FeatureAccessState,
  type FeatureChoice,
  type FeatureDraft,
  type FeatureRow,
} from './feature-access-model';

const DEFAULT_API = createFeatureAccessApi();

function message(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

/** The Files feature (Workspace Files) is Settings › Files', with the other files a workspace gives. */
const FILES_FEATURE = 'files';

/**
 * Settings › Features: one row per enabled feature but Files (Settings › Files), whether the workspace offers it: Everyone or
 * Nobody. A feature is part of the workspace's offer, its access policy "<W> access" (the API
 * writes it as the caller), edited with its agents, apps, workflows and pipelines on that policy's
 * page; a row is editable when IAM lets the caller give the feature here. Other policies naming a
 * feature are listed with it (a Deny wins), and a statement written on the policy's page is shown
 * read-only. Several rows are saved in one step.
 */
export function FeatureAccess({ workspaceId, api = DEFAULT_API }: { workspaceId: string; api?: FeatureAccessApi }) {
  const [state, setState] = useState<FeatureAccessState | null>(null);
  const [error, setError] = useState('');
  const [drafts, setDrafts] = useState<Record<string, FeatureDraft>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setState(await api.read(workspaceId));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read who uses the features.'));
    }
  }, [api, workspaceId]);

  useEffect(() => {
    setState(null);
    setDrafts({});
    setRowErrors({});
    void load();
  }, [load]);

  const rows = useMemo(
    () => sortedRows(state?.features ?? []).filter((row) => row.key !== FILES_FEATURE),
    [state]
  );
  const draftFor = (row: FeatureRow) => drafts[row.key] ?? draftOf(row);
  const changes = changesFrom(rows, drafts);

  const choose = (row: FeatureRow, choice: FeatureChoice) =>
    setDrafts((current): Record<string, FeatureDraft> => ({ ...current, [row.key]: { choice } }));

  const save = async () => {
    setSaving(true);
    try {
      const next = await api.save(workspaceId, changes);
      const refused = next.errors ?? {};
      setState(next);
      setRowErrors(refused);
      setDrafts((current) => Object.fromEntries(Object.entries(current).filter(([key]) => refused[key])));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  const discard = () => {
    setDrafts({});
    setRowErrors({});
  };

  const access = state?.access_policy ?? null;
  const offerHref = access ? ownerHref(access.owner_scope, access.id) : null;

  return (
    <SettingsSection
      title={
        <span className="flex items-center gap-2">
          <SlidersHorizontal size={16} className="text-muted-foreground" />
          Features
        </span>
      }
      description={
        <>
          Whether this workspace offers each feature: Everyone in it, or Nobody. Features are part of what the
          workspace offers, with its agents, apps, workflows and pipelines
          {offerHref && access ? (
            <>
              {' '}
              (<Link href={offerHref}>{access.name}</Link>)
            </>
          ) : null}
          ; each person&apos;s level decides what they may do with them, for everyone, admins included. Other
          policies may grant or deny a feature too, and a Deny always wins. Files are in{' '}
          <Link href={`/workspace/${workspaceId}/settings/files`}>Files</Link>.
        </>
      }
    >
      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}
      {!state ? (
        !error && <p className="text-sm text-muted-foreground">Loading features...</p>
      ) : rows.length === 0 ? (
        <span className="text-sm text-muted-foreground">No features.</span>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="workspace-features-table w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Feature</th>
                  <th className="py-2 pr-3 font-medium">Offered to</th>
                  <th className="py-2 font-medium">Other policies</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const draft = draftFor(row);
                  return (
                    <tr key={row.key} data-feature={row.key} className="border-t border-border align-top">
                      <td className="whitespace-nowrap py-2 pr-3 font-medium text-foreground">{row.label}</td>
                      <td className="py-2 pr-3">
                        <div className="workspace-features-choices" role="radiogroup" aria-label={`Who ${row.label} is offered to`}>
                          {choicesOf(row).map((choice) => (
                            <button
                              key={choice.value}
                              type="button"
                              role="radio"
                              aria-checked={draft.choice === choice.value}
                              data-choice={choice.value}
                              title={choice.hint}
                              disabled={!choice.enabled || saving}
                              className="workspace-features-choice"
                              onClick={() => choose(row, choice.value)}
                            >
                              {choice.label}
                            </button>
                          ))}
                        </div>
                        {rowNotes(row, state).map((note) => (
                          <p key={note.text} className="workspace-features-note" data-tone={note.tone}>
                            {note.text}
                            {note.href && note.link ? (
                              <>
                                {' '}
                                <Link href={note.href}>{note.link}</Link>
                              </>
                            ) : null}
                          </p>
                        ))}
                        {rowErrors[row.key] && (
                          <p className="workspace-features-error" role="alert">
                            {rowErrors[row.key]}
                          </p>
                        )}
                      </td>
                      <td className="py-2">
                        {row.also.length === 0 ? (
                          <span className="text-xs text-muted-foreground">None</span>
                        ) : (
                          <ul className="workspace-features-also">
                            {otherPolicies(row).map(({ policy, text, href }) => (
                              <li key={policy.id} data-effect={policy.effect}>
                                {href ? <Link href={href}>{text}</Link> : text}
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="workspace-features-footer">
            <span className="text-xs text-muted-foreground">
              {changes.length === 0
                ? 'No unsaved change'
                : `${changes.length} unsaved change${changes.length === 1 ? '' : 's'}`}
            </span>
            <button
              type="button"
              className="workspace-features-discard"
              disabled={saving || (changes.length === 0 && Object.keys(rowErrors).length === 0)}
              onClick={discard}
            >
              Discard
            </button>
            <button
              type="button"
              className="workspace-features-save"
              disabled={saving || changes.length === 0}
              onClick={() => void save()}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </>
      )}
    </SettingsSection>
  );
}
