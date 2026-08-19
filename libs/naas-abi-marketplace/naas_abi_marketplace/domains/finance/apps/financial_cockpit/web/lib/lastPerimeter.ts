const LAST_PERIMETER_STORAGE_KEY = 'fin-last-perimeter';

/** Last perimeter the user was on — survives navigation to /admin. */
export function readLastPerimeterId(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    return sessionStorage.getItem(LAST_PERIMETER_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function writeLastPerimeterId(entityId: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    sessionStorage.setItem(LAST_PERIMETER_STORAGE_KEY, entityId);
  } catch {
    /* ignore quota / private mode */
  }
}
