'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { SlidersHorizontal, X } from 'lucide-react';
import { ownerHref } from '@/components/access/policies/policy-owners';
import { SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import { createFeatureAccessApi, type FeatureAccessApi } from './feature-access-api';
import {
  changesFrom,
  choicesOf,
  draftOf,
  draftProblem,
  offeredPrincipals,
  otherPolicies,
  rowNotes,
  sortedRows,
  type FeatureAccessState,
  type FeatureChoice,
  type FeatureDraft,
  type FeatureRow,
  type PrincipalRef,
} from './feature-access-model';

const DEFAULT_API = createFeatureAccessApi();

function message(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function Only({
  row,
  draft,
  candidates,
  disabled,
  onAdd,
  onRemove,
}: {
  row: FeatureRow;
  draft: FeatureDraft;
  candidates: PrincipalRef[] | null;
  disabled: boolean;
  onAdd: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  const known = new Map([...(candidates ?? []), ...row.principals].map((p) => [p.id, p]));
  const offered = offeredPrincipals(candidates ?? [], draft.principals);
  return (
    <div className="workspace-features-only">
      <ul className="workspace-features-chosen" aria-label={`Who may use ${row.label}`}>
        {draft.principals.map((id) => (
          <li key={id} className="workspace-features-chip" data-principal={id}>
            {known.get(id)?.name ?? id}
            {known.get(id)?.kind === 'group' && <span className="text-muted-foreground"> (group)</span>}
            {!disabled && (
              <button type="button" aria-label={`Remove ${known.get(id)?.name ?? id}`} onClick={() => onRemove(id)}>
                <X size={12} />
              </button>
            )}
          </li>
        ))}
      </ul>
      {!disabled &&
        (candidates === null ? (
          <span className="text-xs text-muted-foreground">Loading members and groups...</span>
        ) : (
          <select
            className="workspace-features-add"
            aria-label={`Add who may use ${row.label}`}
            value=""
            onChange={(event) => event.target.value && onAdd(event.target.value)}
          >
            <option value="">{offered.length ? 'Add a member or group…' : 'Nobody else to add'}</option>
            {offered.map((p) => (
              <option key={p.id} value={p.id}>
                {p.kind === 'group' ? `${p.name} (group)` : p.name}
              </option>
            ))}
          </select>
        ))}
    </div>
  );
}

/**
 * General › Features: one row per enabled feature, who may use it here: Everyone, Only… (members
 * and groups) or Nobody. Each choice is a policy the API writes as the caller ("Feature · <name>",
 * attached to the workspace's members, to those chosen, or to nobody), so policies stay the one
 * place access is decided; a row is editable when IAM lets the caller give the feature here. Other
 * policies naming a feature are listed with it (a Deny wins), the ceiling is the workspace's
 * access policy, and a feature's policy changed on its page is shown read-only. Several rows are
 * saved in one step.
 */
export function FeatureAccess({ workspaceId, api = DEFAULT_API }: { workspaceId: string; api?: FeatureAccessApi }) {
  const [state, setState] = useState<FeatureAccessState | null>(null);
  const [error, setError] = useState('');
  const [drafts, setDrafts] = useState<Record<string, FeatureDraft>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [candidates, setCandidates] = useState<PrincipalRef[] | null>(null);

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
    setCandidates(null);
    void load();
  }, [load]);

  const rows = useMemo(() => sortedRows(state?.features ?? []), [state]);
  const draftFor = (row: FeatureRow) => drafts[row.key] ?? draftOf(row);
  const picking = rows.some((row) => row.editable && draftFor(row).choice === 'only');
  const scope = state?.scope;

  useEffect(() => {
    if (!picking || candidates !== null || !scope) return;
    let cancelled = false;
    void api
      .candidates(workspaceId, scope)
      .catch(() => [])
      .then((found) => {
        if (!cancelled) setCandidates(found);
      });
    return () => {
      cancelled = true;
    };
  }, [api, candidates, picking, scope, workspaceId]);

  const changes = changesFrom(rows, drafts);
  const blocked = rows.some((row) => draftProblem(row, drafts[row.key]));

  const update = (row: FeatureRow, next: (draft: FeatureDraft) => FeatureDraft) =>
    setDrafts((current) => ({ ...current, [row.key]: next(current[row.key] ?? draftOf(row)) }));
  const choose = (row: FeatureRow, choice: FeatureChoice) =>
    update(row, (draft) => ({
      choice,
      principals: choice === 'only' ? (draft.choice === 'only' ? draft.principals : draftOf(row).principals) : [],
    }));

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

  const policiesHref = scope ? ownerHref(scope) : null;

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
          Who may use each feature here. Each choice is a policy, Feature · &lt;name&gt;, attached to the
          workspace&apos;s members (Everyone), to the members and groups you choose (Only…) or to nobody. Other
          policies may grant or deny a feature too, and a Deny always wins
          {policiesHref ? (
            <>
              {' '}
              (<Link href={policiesHref}>Access › Policies</Link>)
            </>
          ) : null}
          . Platform administrators see every feature, whatever is chosen here.
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
                  <th className="py-2 pr-3 font-medium">Who may use it</th>
                  <th className="py-2 font-medium">Other policies</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const draft = draftFor(row);
                  const problem = draftProblem(row, drafts[row.key]);
                  return (
                    <tr key={row.key} data-feature={row.key} className="border-t border-border align-top">
                      <td className="whitespace-nowrap py-2 pr-3 font-medium text-foreground">{row.label}</td>
                      <td className="py-2 pr-3">
                        <div className="workspace-features-choices" role="radiogroup" aria-label={`Who may use ${row.label}`}>
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
                        {draft.choice === 'only' && (
                          <Only
                            row={row}
                            draft={draft}
                            candidates={candidates}
                            disabled={!row.editable || saving}
                            onAdd={(id) => update(row, (d) => ({ ...d, principals: [...d.principals, id] }))}
                            onRemove={(id) => update(row, (d) => ({ ...d, principals: d.principals.filter((p) => p !== id) }))}
                          />
                        )}
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
                        {problem && <p className="workspace-features-note" data-tone="warning">{problem}</p>}
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
              disabled={saving || changes.length === 0 || blocked}
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
