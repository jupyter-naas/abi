/**
 * System files: any entry whose name starts with "." (.gitkeep, .env, .abi/…),
 * or anything inside such a folder. Files hides them unless View → Show
 * system files is on, and never offers to edit them — the API refuses writes
 * to them too, so this is the UI half of the same rule.
 */

export function isSystemFileName(name: string): boolean {
  return name.startsWith('.');
}

/** True when any segment of the path is a system name. */
export function isSystemPath(path: string): boolean {
  return path.split('/').some((segment) => segment !== '' && isSystemFileName(segment));
}

/** Drop system entries from a listing unless they were asked for. */
export function withoutSystemFiles<T extends { name: string }>(files: T[], show: boolean): T[] {
  return show ? files : files.filter((file) => !isSystemFileName(file.name));
}
