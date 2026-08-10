/**
 * Authors pinned to the sidebar.
 *
 * Pins are a working set — the handles someone comes back to across sessions —
 * so unlike the timezone they live in ``localStorage`` rather than in the
 * session. Blocked storage (private mode, embedded frames) degrades to pins
 * that simply do not survive a reload.
 */

const PINS_KEY = "x.apps.x.pinnedUsers";

/** Kept small: the sidebar is quick access, not a second search page. */
export const MAX_PINNED_USERS = 12;

export function readPinnedUsers(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(PINS_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((value): value is string => typeof value === "string" && !!value)
      .slice(0, MAX_PINNED_USERS);
  } catch {
    return [];
  }
}

export function writePinnedUsers(usernames: string[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      PINS_KEY,
      JSON.stringify(usernames.slice(0, MAX_PINNED_USERS)),
    );
  } catch {
    // Private mode / blocked storage — the pins stay in memory only.
  }
}

/**
 * ``usernames`` with ``username`` added or removed.
 *
 * A new pin goes to the front, so the most recently pinned author is the first
 * one in the sidebar, and the oldest falls off once the list is full.
 */
export function togglePinned(usernames: string[], username: string): string[] {
  if (usernames.includes(username)) {
    return usernames.filter((name) => name !== username);
  }
  return [username, ...usernames].slice(0, MAX_PINNED_USERS);
}
