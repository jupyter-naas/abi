"use client";

import type { TimezoneEntry } from "@/lib/types";

type Props = {
  timezones: TimezoneEntry[];
  timezone: string;
  onTimezoneChange: (id: string) => void;
};

export function ParametersPage({
  timezones,
  timezone,
  onTimezoneChange,
}: Props) {
  return (
    <div className="params">
      <div className="section-head">
        <h2>Timezone</h2>
        <p className="sub">
          Used when formatting tweet timestamps on the Search page. Saved for
          this browser session only.
        </p>
      </div>
      <div className="card params-card">
        <div className="field field-start">
          <label htmlFor="tz-select">Display timezone</label>
          <select
            id="tz-select"
            value={timezone}
            onChange={(e) => onTimezoneChange(e.target.value)}
          >
            {timezones.map((tz) => (
              <option key={tz.id} value={tz.id}>
                {tz.label}
              </option>
            ))}
          </select>
        </div>
        <p className="params-hint">
          Current value: <strong>{timezone}</strong>
        </p>
      </div>
    </div>
  );
}
