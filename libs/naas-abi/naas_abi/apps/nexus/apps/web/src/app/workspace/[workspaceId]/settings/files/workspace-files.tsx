'use client';

import { useCallback, useEffect, useState } from 'react';
import { SettingsNotice, SettingsPageHeader, SettingsSection } from '@/components/settings/settings-ui';
import {
  createOfferApi,
  type FileMode,
  type FileRow,
  type OfferApi,
  type OfferState,
} from '@/lib/access-model/workspace-offer';
import { createFeatureAccessApi, type FeatureAccessApi } from '../features/feature-access-api';
import type { FeatureAccessState, FeatureRow } from '../features/feature-access-model';

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
 * Read); My Files is a setting of the deployment, shown. Each change is saved at once, through IAM as
 * the caller: a choice they may not give is disabled, with why.
 */
export function WorkspaceFiles({
  workspaceId,
  offerApi = DEFAULT_OFFER_API,
  featureApi = DEFAULT_FEATURE_API,
  description,
}: {
  workspaceId: string;
  offerApi?: OfferApi;
  featureApi?: FeatureAccessApi;
  /** The page's line under its title. */
  description?: string;
}) {
  const [offer, setOffer] = useState<OfferState | null>(null);
  const [features, setFeatures] = useState<FeatureAccessState | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextOffer, nextFeatures] = await Promise.all([
        offerApi.read(workspaceId),
        featureApi.read(workspaceId).catch(() => null),
      ]);
      setOffer(nextOffer);
      setFeatures(nextFeatures);
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read the files of this workspace.'));
    }
  }, [offerApi, featureApi, workspaceId]);

  useEffect(() => {
    setOffer(null);
    setFeatures(null);
    setNotice('');
    void load();
  }, [load]);

  const run = async (work: () => Promise<void>, done: string) => {
    setSaving(true);
    try {
      await work();
      setError('');
      setNotice(done);
    } catch (e) {
      setNotice('');
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  const workspaceFiles: FeatureRow | null = features?.features.find((row) => row.key === FILES_FEATURE) ?? null;
  const workspaceFilesOn = workspaceFiles?.choice === 'everyone';

  const toggleWorkspaceFiles = (on: boolean) =>
    void run(async () => {
      if (!workspaceFiles) return;
      const next = await featureApi.save(workspaceId, [{ feature: FILES_FEATURE, choice: on ? 'everyone' : 'nobody' }]);
      const refused = next.errors?.[FILES_FEATURE];
      setFeatures(next);
      if (refused) throw new Error(refused);
    }, `Workspace Files: ${on ? 'Everyone' : 'Nobody'}.`);

  const chooseMode = (row: FileRow, mode: FileMode) =>
    void run(async () => {
      if (mode === row.mode) return;
      setOffer(await offerApi.saveFiles(workspaceId, { [row.key]: mode }));
    }, `${row.label}: ${MODE_LABELS[mode]}.`);

  // One total: the kinds of files listed (Workspace, Organization, Platform, System, My Files).
  const kinds = offer ? 1 + (offer.files ?? []).length + (offer.my_files ? 1 : 0) : null;

  return (
    <>
    <SettingsPageHeader
      title="Files"
      badge={kinds === null ? undefined : `${kinds} kind${kinds === 1 ? '' : 's'} of files`}
      description={description}
    />
    <SettingsSection>
      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}
      {notice && (
        <p className="text-xs text-muted-foreground" role="status" data-files-notice="">
          {notice}
        </p>
      )}
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
                            onClick={() => workspaceFilesOn !== on && toggleWorkspaceFiles(on)}
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
                          aria-checked={row.mode === mode}
                          data-choice={mode}
                          title={MODE_HINTS[mode]}
                          disabled={!row.editable || !row.choices.includes(mode) || saving}
                          className="workspace-features-choice"
                          onClick={() => chooseMode(row, mode)}
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
    </SettingsSection>
    </>
  );
}
