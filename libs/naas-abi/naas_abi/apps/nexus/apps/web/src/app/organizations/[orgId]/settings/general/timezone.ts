/**
 * Organization Settings › General › Timezone, the pure part: the IANA names the select
 * offers, the value read from `GET /api/organizations/<id>`, and the PATCH body when it
 * changed. Analytics periods (Today, This week…) start at midnight in this timezone.
 */

export const DEFAULT_TIMEZONE = 'UTC';

/** Offered when the browser cannot list its timezones (`Intl.supportedValuesOf`). */
export const FALLBACK_TIMEZONES: readonly string[] = [
  'UTC',
  'Africa/Cairo',
  'Africa/Johannesburg',
  'Africa/Lagos',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Mexico_City',
  'America/New_York',
  'America/Sao_Paulo',
  'America/Toronto',
  'Asia/Dubai',
  'Asia/Hong_Kong',
  'Asia/Kolkata',
  'Asia/Shanghai',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
  'Europe/Amsterdam',
  'Europe/Berlin',
  'Europe/Brussels',
  'Europe/London',
  'Europe/Madrid',
  'Europe/Paris',
  'Europe/Rome',
  'Europe/Zurich',
  'Pacific/Auckland',
];

type SupportedValuesOf = (key: 'timeZone') => string[];

/**
 * The IANA names the select offers: the browser's list (UTC first, then by name), or the
 * fallback list. `current` is always offered, so a saved value the list lacks stays shown.
 */
export function timezoneOptions(
  current?: string | null,
  /** The browser's lister; null when there is none. */
  supportedValuesOf: SupportedValuesOf | null = (Intl as { supportedValuesOf?: SupportedValuesOf }).supportedValuesOf ??
    null
): string[] {
  let listed: string[] = [];
  try {
    listed = supportedValuesOf ? supportedValuesOf('timeZone') : [];
  } catch {
    listed = [];
  }
  const names = new Set(listed.length > 0 ? listed : FALLBACK_TIMEZONES);
  if (current) names.add(current);
  names.delete(DEFAULT_TIMEZONE);
  return [DEFAULT_TIMEZONE, ...[...names].sort((a, b) => a.localeCompare(b))];
}

/** The organization's timezone from its API body: `UTC` when missing or blank. */
export function timezoneFrom(data: { timezone?: unknown } | null | undefined): string {
  const value = data?.timezone;
  return typeof value === 'string' && value.trim() ? value.trim() : DEFAULT_TIMEZONE;
}

/** The PATCH body part for the timezone: `{ timezone }` when it changed, else nothing. */
export function timezoneChange(initial: string, current: string): { timezone?: string } {
  return initial === current ? {} : { timezone: current };
}

/** A timezone's label in the select: its name and current UTC offset ("Europe/Paris (UTC+01:00)"). */
export function timezoneLabel(timeZone: string, at: Date = new Date()): string {
  try {
    const part = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'longOffset' })
      .formatToParts(at)
      .find((p) => p.type === 'timeZoneName')?.value;
    const offset = !part || part === 'GMT' ? 'UTC' : part.replace('GMT', 'UTC');
    return timeZone === DEFAULT_TIMEZONE ? timeZone : `${timeZone} (${offset})`;
  } catch {
    return timeZone;
  }
}
