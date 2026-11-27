'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Save } from 'lucide-react';
import { usePageDraft } from '@/hooks/use-page-state';
import { SettingsPageHeader } from '@/components/settings/settings-ui';
import { Notice } from '@/components/ui/notice';
import { Card } from '@/components/ui/card';
import {
  createOfferApi,
  type FileMode,
  type FileRow,
  type OfferApi,
  type OfferState,
} from '@/lib/access-model/workspace-offer';
import { createFeatureAccessApi, type FeatureAccessApi } from '../features/feature-access-api';
import type { FeatureAccessState, FeatureRow } from '../features/feature-access-model';

// The unsaved-changes bar of the General pages, and their Save button.
import '@/app/organizations/[orgId]/settings/general/general.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import { usePolicyViewStore } from '@/components/settings/settings-policy-picker';

const DEFAULT_OFFER_API = createOfferApi();
const DEFAULT_FEATURE_API = createFeatureAccessApi();
/** The feature that is the workspace's own files (Workspace Files). */
export const FILES_FEATURE = 'files';

const MODE_LABELS: Record<FileMode, string> = { off: 'Off', read: 'Read', write: 'Read and write' };
const MODE_HINTS: Record<FileMode, string> = {
  off: 'The people of this workspace do not get these files from it',
  read: 'They list and read these files',
  write: 'Members also write and delete them; Viewers read them',
};

function message(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

/**
 * Settings › Files: every kind of files the people of a workspace open, in one place, each within their
 * level. Workspace Files is the workspace's `files` feature (Everyone or Nobody); Organization, Platform
 * and System Files are the given sections of its offer (Off, Read, Read and write; System Files Off or
 * Read); My Files is a setting of the deployment, shown. A form: the choices wait for Save (faded until
 * something changes), the unsaved bar says so, and they are kept for a return to the page
 * (`usePageDraft`); Save writes them through IAM as the caller: a choice they may not give is
 * disabled, with why.
 */
export function WorkspaceFiles({
  workspaceId,
  offerApi = DEFAULT_OFFER_API,
  featureApi = DEFAULT_FEATURE_API,
  description,
  policyId = null,
}: {
  workspaceId: string;
  /** The policy picked in the Settings column (`?policy=`); "<W> access" when null. */
  policyId?: string | null;
  offerApi?: OfferApi;
  featureApi?: FeatureAccessApi;
  /** The page's line under its title. */
  description?: string;
}) {
  const [offer, setOffer] = useState<OfferState | null>(null);
  const [features, setFeatures] = useState<FeatureAccessState | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextOffer, nextFeatures] = await Promise.all([
        offerApi.read(workspaceId, policyId),
        featureApi.read(workspaceId, policyId).catch(() => null),
      ]);
      setOffer(nextOffer);
      setFeatures(nextFeatures);
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read the files of this workspace.'));
    }
  }, [offerApi, featureApi, workspaceId, policyId]);

  useEffect(() => {
    setOffer(null);
    setFeatures(null);
    void load();
  }, [load]);

  const workspaceFiles: FeatureRow | null = features?.features.find((row) => row.key === FILES_FEATURE) ?? null;

  // What the workspace holds (`workspace`: Workspace Files, Everyone or Nobody; a mode per section
  // of files), and the choices made over it, kept for a return to the page.
  const server = useMemo(() => {
    if (!offer) return null;
    const record: Record<string, string> = Object.fromEntries((offer.files ?? []).map((row) => [row.key, row.mode]));
    if (workspaceFiles) record.workspace = workspaceFiles.choice === 'everyone' ? 'everyone' : 'nobody';
    return record;
  }, [offer, workspaceFiles]);
  const draft = usePageDraft(
    workspaceId ? { scope: `workspace:${workspaceId}`, page: 'files', detail: policyId ?? undefined } : null,
    server
  );
  const values = draft.values ?? server ?? {};
  const changed = Object.keys(values).filter((key) => server && values[key] !== server[key]);
  const dirty = changed.length > 0;
  const workspaceFilesOn = values.workspace === 'everyone';

  const choose = (key: string, value: string) => {
    setSaved(false);
    draft.set({ [key]: value });
  };

  /** Save: Workspace Files through the feature, then the sections of files in one write of the offer. */
  const save = async () => {
    setSaving(true);
    setError('');
    try {
      if (changed.includes('workspace') && workspaceFiles) {
        const next = await featureApi.save(
          workspaceId,
          [{ feature: FILES_FEATURE, choice: workspaceFilesOn ? 'everyone' : 'nobody' }],
          policyId
        );
        setFeatures(next);
        // The column's Features group follows what the policy grants: read again.
        usePolicyViewStore.getState().forget(workspaceId);
        const refused = next.errors?.[FILES_FEATURE];
        if (refused) throw new Error(refused);
      }
      const modes = Object.fromEntries(changed.filter((key) => key !== 'workspace').map((key) => [key, values[key]]));
      if (Object.keys(modes).length > 0) {
        setOffer(await offerApi.saveFiles(workspaceId, modes as Partial<Record<FileRow['key'], FileMode>>, policyId));
      }
      draft.discard();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  // One total: the kinds of files listed (Workspace, Organization, Platform, System, My Files).
  const kinds = offer ? 1 + (offer.files ?? []).length + (offer.my_files ? 1 : 0) : null;

  return (
    <>
    <SettingsPageHeader
      title="Files"
      badge={kinds === null ? undefined : `${kinds} kind${kinds === 1 ? '' : 's'} of files`}
      description={description}
      actions={
        // The button of the General pages: faded until something changes.
        <button
          type="button"
          onClick={() => void save()}
          disabled={!dirty || saving}
          data-action="save"
          className={saved ? 'org-settings-primary-button org-settings-primary-button-saved' : 'org-settings-primary-button'}
        >
          <Save size={16} />
          {saved ? 'Saved!' : saving ? 'Saving...' : 'Save changes'}
        </button>
      }
    />
    {error && <Notice tone="error">{error}</Notice>}
    {dirty ? (
      <div className="org-settings-general-draft" role="status">
        <p className="org-settings-general-draft-text">
          {draft.conflicts.length > 0 ? 'Changed elsewhere since you began editing: saving keeps your choices.' : 'Unsaved changes.'}
        </p>
        <button
          type="button"
          onClick={() => {
            draft.discard();
            setError('');
          }}
          disabled={saving}
          className="org-settings-general-draft-discard"
        >
          Discard changes
        </button>
      </div>
    ) : null}
    <Card>
      {!offer ? (
        !error && <p className="text-sm text-muted-foreground">Loading files...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="workspace-features-table w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Files</th>
                <th className="py-2 font-medium">Given here</th>
              </tr>
            </thead>
            <tbody>
              <tr data-files="workspace" className="border-t border-border align-top">
                <td className="whitespace-nowrap py-2 pr-3 font-medium text-foreground">Workspace Files</td>
                <td className="py-2">
                  {workspaceFiles ? (
                    <>
                      <div className="workspace-features-choices" role="radiogroup" aria-label="Workspace Files">
                        {([true, false] as const).map((on) => (
                          <button
                            key={String(on)}
                            type="button"
                            role="radio"
                            aria-checked={workspaceFilesOn === on}
                            data-choice={on ? 'everyone' : 'nobody'}
                            disabled={!workspaceFiles.editable || saving}
                            className="workspace-features-choice"
                            onClick={() => choose('workspace', on ? 'everyone' : 'nobody')}
                          >
                            {on ? 'Everyone' : 'Nobody'}
                          </button>
                        ))}
                      </div>
                      <p className="workspace-features-note">The workspace&apos;s own files.</p>
                      {!workspaceFiles.editable && workspaceFiles.reason && (
                        <p className="workspace-features-note">{workspaceFiles.reason}</p>
                      )}
                    </>
                  ) : (
                    <p className="workspace-features-note">The Files feature is not enabled on this deployment.</p>
                  )}
                </td>
              </tr>
              {(offer.files ?? []).map((row) => (
                <tr key={row.key} data-files={row.key} className="border-t border-border align-top">
                  <td className="whitespace-nowrap py-2 pr-3 font-medium text-foreground">{row.label}</td>
                  <td className="py-2">
                    <div className="workspace-features-choices" role="radiogroup" aria-label={row.label}>
                      {row.modes.map((mode) => (
                        <button
                          key={mode}
                          type="button"
                          role="radio"
                          aria-checked={values[row.key] === mode}
                          data-choice={mode}
                          title={MODE_HINTS[mode]}
                          disabled={!row.editable || !row.choices.includes(mode) || saving}
                          className="workspace-features-choice"
                          onClick={() => choose(row.key, mode)}
                        >
                          {MODE_LABELS[mode]}
                        </button>
                      ))}
                    </div>
                    {!row.editable && row.reason && <p className="workspace-features-note">{row.reason}</p>}
                  </td>
                </tr>
              ))}
              {offer.my_files && (
                <tr data-files="my_files" className="border-t border-border align-top">
                  <td className="whitespace-nowrap py-2 pr-3 font-medium text-foreground">My Files</td>
                  <td className="py-2">
                    <p className="workspace-features-note">
                      {`Every Member writes theirs; Viewers ${
                        offer.my_files.viewers === 'read' ? 'read theirs' : 'have none'
                      }. A setting of the deployment, not of the workspace.`}
                    </p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </Card>
    </>
  );
}
