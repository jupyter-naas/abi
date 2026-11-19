/**
 * Platform Settings › Drives: the pure part (the row's words, the API's words for a
 * refusal). No React: the middleware reads the path too.
 */

/** Platform Settings › Drives. */
export const PLATFORM_DRIVES_PATH = '/settings/drives';

export type DriveStatus = 'reachable' | 'unreachable';

/** A part of where a drive keeps its files (`bucket`: `abi`). */
export interface DriveLocationPart {
  label: string;
  value: string;
}

/** A drive as `GET /api/platform/drives` answers it: never a credential. */
export interface PlatformDrive {
  id: string;
  name: string;
  type: string;
  provider: string;
  /** The configured adapter (`s3`, `fs`…). */
  adapter: string;
  location: DriveLocationPart[];
  status: DriveStatus;
}

export function driveCount(n: number): string {
  return `${n} ${n === 1 ? 'drive' : 'drives'}`;
}

/** "bucket abi, prefix datastore", or "" when the drive names no location. */
export function driveLocationText(drive: Pick<PlatformDrive, 'location'>): string {
  return drive.location.map((part) => `${part.label} ${part.value}`).join(', ');
}

export function driveStatusLabel(status: DriveStatus): string {
  return status === 'reachable' ? 'Reachable' : 'Unreachable';
}

export function errorText(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (status === 403) return 'Only a platform admin can list the drives.';
  if (status === 0) return 'The API did not answer.';
  return `The API answered ${status}.`;
}
