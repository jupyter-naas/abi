import { readStored, writeStored } from "@/lib/storage";

const TIMEZONE_SESSION_KEY = "x.apps.x_proxy.timezone";

export function readSessionTimezone(): string | null {
  const value = readStored("session", TIMEZONE_SESSION_KEY);
  return value && value.trim() ? value : null;
}

export function writeSessionTimezone(timezone: string): void {
  writeStored("session", TIMEZONE_SESSION_KEY, timezone);
}
