'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Archive, RefreshCw } from 'lucide-react';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import { listDrives, type Fetcher } from './drives-api';
import { driveCount, driveStatusLabel, type PlatformDrive } from './drives-model';
import '../users/users.css';
import './drives.css';

const COLUMNS = ['Name', 'Type', 'Provider', 'Location', 'Status'];

function DriveRow({ drive }: { drive: PlatformDrive }) {
  return (
    <tr data-drive={drive.id}>
      <td>
        <div className="org-settings-users-row-start">
          <div className="org-settings-users-avatar">
            <Archive size={16} />
          </div>
          <div className="org-settings-users-identity">
            <p className="org-settings-users-name" data-field="name">
              {drive.name}
            </p>
            <p className="org-settings-users-email platform-users-mono">{drive.adapter}</p>
          </div>
        </div>
      </td>
      <td data-field="type">{drive.type}</td>
      <td data-field="provider">{drive.provider}</td>
      <td data-field="location">
        {drive.location.length === 0 ? (
          <span className="platform-users-muted">—</span>
        ) : (
          <span className="platform-drives-location">
            {drive.location.map((part) => (
              <span key={part.label} className="platform-drives-location-part">
                <span className="platform-users-muted">{part.label}</span>{' '}
                <code className="platform-users-mono">{part.value}</code>
              </span>
            ))}
          </span>
        )}
      </td>
      <td>
        <span className={`platform-drives-status is-${drive.status}`} data-field="status">
          {driveStatusLabel(drive.status)}
        </span>
      </td>
    </tr>
  );
}

/**
 * The platform's drives, read-only: where files are stored, as the engine configures them, and
 * whether each storage answers. Access keys and secrets stay in the configuration.
 */
export function PlatformDrives({ fetcher }: { fetcher?: Fetcher }) {
  const [drives, setDrives] = useState<PlatformDrive[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloads, setReloads] = useState(0);

  const reload = useCallback(() => setReloads((n) => n + 1), []);

  useEffect(() => {
    let live = true;
    setLoading(true);
    void listDrives(fetcher).then((answer) => {
      if (!live) return;
      setLoading(false);
      if (answer.ok) {
        setDrives(answer.data);
        setLoadError(null);
      } else {
        setDrives(null);
        setLoadError(answer.error);
      }
    });
    return () => {
      live = false;
    };
  }, [fetcher, reloads]);

  return (
    <div className="org-settings-users-page platform-users-page platform-drives-page">
      <div className="org-settings-users-main">
        <OrgSettingsPageHeader
          title="Drives"
          badge={drives ? driveCount(drives.length) : undefined}
          subtitle="Where the platform stores files, as its configuration sets them, and whether each storage answers"
          actions={
            <button
              type="button"
              className="org-settings-users-secondary-button"
              data-action="refresh"
              onClick={reload}
              disabled={loading}
              title="Refresh"
              aria-label="Refresh"
            >
              <RefreshCw size={16} />
            </button>
          }
        />

        {loadError && (
          <div className="org-settings-users-alert" role="alert">
            <AlertCircle size={16} />
            <span>{loadError}</span>
          </div>
        )}

        <div className="org-settings-users-table-wrap">
          {drives === null && !loadError ? (
            <div className="org-settings-loading">Loading drives…</div>
          ) : drives !== null && drives.length === 0 ? (
            <div className="org-settings-empty">
              <div className="org-settings-empty-icon">
                <Archive size={24} />
              </div>
              <p className="org-settings-empty-title">No drives configured</p>
            </div>
          ) : drives !== null ? (
            <table className="org-settings-users-table">
              <thead>
                <tr>
                  {COLUMNS.map((column) => (
                    <th key={column}>
                      <div className="org-settings-users-th">
                        <span>{column}</span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {drives.map((drive) => (
                  <DriveRow key={drive.id} drive={drive} />
                ))}
              </tbody>
            </table>
          ) : null}
        </div>

        <p className="org-settings-footnote">
          Drives are set in the platform&apos;s configuration (<code>services.object_storage</code>). Who
          opens which folder of a drive is decided by roles and policies. The status is one small read
          against the storage, made when the page opens.
        </p>
      </div>
    </div>
  );
}

export default function PlatformDrivesPage() {
  return <PlatformDrives />;
}
