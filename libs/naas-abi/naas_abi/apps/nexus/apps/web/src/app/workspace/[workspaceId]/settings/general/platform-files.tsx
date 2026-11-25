'use client';

import { useEffect, useState } from 'react';
import { HardDrive } from 'lucide-react';
import { SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import {
  createPlatformFilesApi,
  PlatformFilesError,
  type PlatformFilesApi,
  type PlatformFilesMode,
  type PlatformFilesState,
} from './platform-files-api';

const DEFAULT_API = createPlatformFilesApi();

const MODES: { value: PlatformFilesMode; label: string; hint: string }[] = [
  { value: 'off', label: 'Off', hint: 'The people of this workspace do not get Platform Files from it' },
  { value: 'read', label: 'Read', hint: 'They list and read Platform Files' },
  { value: 'write', label: 'Read and write', hint: 'Members also write and delete Platform Files; Viewers read them' },
];

function message(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

/**
 * General › Platform Files: Off, Read, or Read and write for everyone in the workspace, within each one's
 * level (the `GivenPlatformFiles` section of the workspace's offer, also shown in its Configuration).
 * Read-only unless the caller may change it (a platform admin; a workspace admin may narrow it); hidden
 * for someone who may not read the workspace's configuration.
 */
export function PlatformFiles({ workspaceId, api = DEFAULT_API }: { workspaceId: string; api?: PlatformFilesApi }) {
  const [state, setState] = useState<PlatformFilesState | null>(null);
  const [hidden, setHidden] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setState(null);
    setHidden(false);
    setError('');
    api.read(workspaceId).then(
      (found) => {
        if (!cancelled) setState(found);
      },
      (e: unknown) => {
        if (cancelled) return;
        if (e instanceof PlatformFilesError && (e.status === 403 || e.status === 404)) setHidden(true);
        else setError(message(e, 'Could not read Platform Files.'));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [api, workspaceId]);

  if (hidden) return null;

  const choose = async (mode: PlatformFilesMode) => {
    if (!state || mode === state.mode) return;
    setSaving(true);
    try {
      setState(await api.save(workspaceId, mode));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsSection
      title={
        <span className="flex items-center gap-2">
          <HardDrive size={16} className="text-muted-foreground" />
          Platform Files
        </span>
      }
      description="The files shared by the whole platform. Whether everyone in this workspace may open them, and change them."
    >
      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}
      {!state ? (
        !error && <p className="text-sm text-muted-foreground">Loading Platform Files...</p>
      ) : (
        <>
          <div className="workspace-features-choices" role="radiogroup" aria-label="Platform Files for this workspace">
            {MODES.map((mode) => (
              <button
                key={mode.value}
                type="button"
                role="radio"
                aria-checked={state.mode === mode.value}
                data-platform-files={mode.value}
                title={mode.hint}
                disabled={!state.can_change || saving}
                className="workspace-features-choice"
                onClick={() => void choose(mode.value)}
              >
                {mode.label}
              </button>
            ))}
          </div>
          {!state.can_change && (
            <p className="workspace-features-note">Only a platform admin can change it.</p>
          )}
        </>
      )}
    </SettingsSection>
  );
}
