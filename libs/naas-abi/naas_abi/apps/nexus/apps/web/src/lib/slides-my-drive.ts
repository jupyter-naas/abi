import { parseFastApiDetail } from '@/lib/create-slides-project';
import { authFetch } from '@/stores/auth';

/** User-relative folder in My Drive. The files API prefixes `naas_abi/my-drive/<user_id>/`. */
export function myDriveSlidesDir(slug: string): string {
  return `slides/${slug}`;
}

export function myDriveDeckRelativePath(slug: string): string {
  return `${myDriveSlidesDir(slug)}/deck.html`;
}

export function myDriveProjectRelativePath(slug: string): string {
  return `${myDriveSlidesDir(slug)}/project.json`;
}

const INFRA_RE =
  /minio|s3|boto|endpoint|bucket|object storage|connection refused|econnrefused|timeout/i;

/** Short File/status error. Never surface storage internals. */
export function myDriveCopyErrorMessage(detail: unknown, status: number): string {
  if (status === 401 || status === 403 || status >= 500 || status === 0) {
    return 'My Drive is unavailable.';
  }
  if (status === 413) {
    return 'Deck is too large for My Drive.';
  }
  const raw = parseFastApiDetail(detail);
  if (!raw || INFRA_RE.test(raw) || raw.length > 80) {
    return 'Could not copy to My Drive.';
  }
  return raw;
}

export async function uploadFileToMyDrive(
  dir: string,
  file: File,
): Promise<{ path: string; name: string }> {
  const form = new FormData();
  form.append('file', file);
  form.append('path', dir);
  form.append('scope', 'my_drive');

  const res = await authFetch('/api/files/upload', {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(myDriveCopyErrorMessage(body.detail, res.status));
  }
  return (await res.json()) as { path: string; name: string };
}

export async function copyDeckToMyDrive(opts: {
  slug: string;
  html: string;
  title?: string;
  workspaceId?: string;
}): Promise<{ relativePath: string }> {
  if (!opts.slug || !opts.html) {
    throw new Error('Could not copy to My Drive.');
  }

  const dir = myDriveSlidesDir(opts.slug);
  const deck = new File([opts.html], 'deck.html', { type: 'text/html;charset=utf-8' });
  await uploadFileToMyDrive(dir, deck);

  const project = {
    title: opts.title || opts.slug,
    slug: opts.slug,
    ...(opts.workspaceId ? { workspace_id: opts.workspaceId } : {}),
  };
  try {
    const json = new File([JSON.stringify(project, null, 2)], 'project.json', {
      type: 'application/json',
    });
    await uploadFileToMyDrive(dir, json);
  } catch {
    // deck.html is the required copy; project.json is best-effort
  }

  return { relativePath: myDriveDeckRelativePath(opts.slug) };
}
