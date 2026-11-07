'use client';

/**
 * Detach, asked first: the one control every access table uses (a person's page, a group's,
 * where a policy is attached). ``confirming`` is whether this row asks now; the table keeps
 * which row that is, so one asks at a time.
 */
export function ConfirmDetach({
  label,
  confirming,
  onAsk,
  onKeep,
  onConfirm,
}: {
  /** What the Detach button says to assistive technology: what, from whom, where. */
  label: string;
  confirming: boolean;
  onAsk: () => void;
  onKeep: () => void;
  onConfirm: () => void;
}) {
  if (!confirming) {
    return (
      <button type="button" className="access-button" aria-label={label} onClick={onAsk}>
        Detach
      </button>
    );
  }
  return (
    <span className="access-holding-confirm">
      <button type="button" className="access-button access-holding-danger" onClick={onConfirm}>
        Confirm detach
      </button>
      <button type="button" className="access-button" onClick={onKeep}>
        Keep
      </button>
    </span>
  );
}
