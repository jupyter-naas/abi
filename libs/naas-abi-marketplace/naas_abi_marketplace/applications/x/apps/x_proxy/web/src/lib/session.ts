const TIMEZONE_SESSION_KEY = "x.apps.x_proxy.timezone";

export function readSessionTimezone(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.sessionStorage.getItem(TIMEZONE_SESSION_KEY);
    return value && value.trim() ? value : null;
  } catch {
    return null;
  }
}

export function writeSessionTimezone(timezone: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(TIMEZONE_SESSION_KEY, timezone);
  } catch {
    // Private mode / blocked storage — ignore.
  }
}
