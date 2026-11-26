'use client';

/**
 * A feature's or a core service's access level (None, Read, Write, Admin, those it has), and the
 * actions each level brings, unfolded on demand. Styles: `workspace-features-*` (General's CSS).
 */
import { LEVEL_LABELS, levelHint, type AccessLevel, type LevelRow } from '@/lib/access-model/access-levels';

export function AccessLevelChoice({
  row,
  value,
  mode,
  disabled = false,
  hideNone = false,
  onChange,
}: {
  row: LevelRow;
  value: AccessLevel;
  mode: 'cap' | 'grant';
  disabled?: boolean;
  /** Without None (a feature's Nobody already says it), unless it is the level now. */
  hideNone?: boolean;
  onChange: (level: AccessLevel) => void;
}) {
  const choices = row.choices.filter((level) => !(hideNone && level === 'none' && value !== 'none'));
  const brought = (['read', 'write', 'admin'] as const).filter((level) => row.actions[level]?.length);
  return (
    <div data-access-level={row.key}>
      <div className="workspace-features-choices" role="radiogroup" aria-label={`Access to ${row.label}`}>
        {choices.map((level) => (
          <button
            key={level}
            type="button"
            role="radio"
            aria-checked={value === level}
            data-level={level}
            title={levelHint(level, mode)}
            disabled={disabled}
            className="workspace-features-choice"
            onClick={() => value !== level && onChange(level)}
          >
            {LEVEL_LABELS[level]}
          </button>
        ))}
      </div>
      {brought.length > 0 && (
        <details className="workspace-features-note" data-level-actions="">
          <summary>Actions</summary>
          <ul>
            {brought.map((level) => (
              <li key={level}>
                <strong>{LEVEL_LABELS[level]}:</strong> {(row.actions[level] ?? []).join(', ')}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
