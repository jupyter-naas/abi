'use client';

/** The keyboard map, opened with ``?``. */
import { Keyboard } from 'lucide-react';
import { Kbd } from './data-ui';
import { Modal } from './modal';

export const SHORTCUTS: { keys: string[]; label: string }[] = [
  { keys: ['/'], label: 'Search' },
  { keys: ['↑', '↓'], label: 'Move through entries (also k and j)' },
  { keys: ['↵'], label: 'Open the selected entry' },
  { keys: ['⌫'], label: 'Up one level' },
  { keys: ['Esc'], label: 'Close the inspector' },
  { keys: ['N'], label: 'New entry' },
  { keys: ['E'], label: 'Edit the open entry' },
  { keys: ['D'], label: 'Download the open entry' },
  { keys: ['R'], label: 'Refresh' },
  { keys: ['⌘', '⌫'], label: 'Delete the open entry' },
  { keys: ['⌘', 'S'], label: 'Save in the editor' },
  { keys: ['?'], label: 'This list' },
];

export function ShortcutsSheet({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="Keyboard shortcuts" icon={<Keyboard size={18} />} onClose={onClose}>
      <dl className="data-shortcuts">
        {SHORTCUTS.map((s) => (
          <div key={s.label} className="data-shortcut">
            <dt>{s.label}</dt>
            <dd>
              {s.keys.map((k) => (
                <Kbd key={k}>{k}</Kbd>
              ))}
            </dd>
          </div>
        ))}
      </dl>
    </Modal>
  );
}
