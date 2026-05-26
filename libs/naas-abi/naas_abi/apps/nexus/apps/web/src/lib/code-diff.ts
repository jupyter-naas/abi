export interface CodeDiffInfo {
  additions: number;
  deletions: number;
  status: string;
  before?: string;
  after?: string;
  patch?: string;
}

export interface CodeDiffEntry {
  file: string;
  additions: number;
  deletions: number;
  status: string;
  before?: string;
  after?: string;
  patch?: string;
}

/** Match a sandbox path to a key in the OpenCode diff map. */
export function findCodeDiffKey(
  diffs: Record<string, CodeDiffInfo>,
  path: string,
): string | undefined {
  if (diffs[path]) return path;
  const filename = path.split('/').pop() ?? path;
  for (const [key] of Object.entries(diffs)) {
    if (
      path === key
      || path.endsWith(`/${key}`)
      || key.endsWith(`/${filename}`)
      || path.endsWith(key)
      || key.endsWith(path)
      || key.endsWith(filename)
    ) {
      return key;
    }
  }
  return undefined;
}

export function normalizeDiffText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value == null) return '';
  return String(value);
}

export function resolveDiffContents(
  diff: CodeDiffInfo | undefined,
  diskContent: string,
): { before: string; after: string } {
  const disk = normalizeDiffText(diskContent);
  if (!diff) {
    return { before: disk, after: disk };
  }

  if (diff.status === 'added') {
    return {
      before: normalizeDiffText(diff.before),
      after: normalizeDiffText(diff.after) || disk,
    };
  }
  if (diff.status === 'deleted') {
    return {
      before: normalizeDiffText(diff.before) || disk,
      after: normalizeDiffText(diff.after),
    };
  }
  return {
    before: normalizeDiffText(diff.before),
    after: normalizeDiffText(diff.after) || disk,
  };
}
