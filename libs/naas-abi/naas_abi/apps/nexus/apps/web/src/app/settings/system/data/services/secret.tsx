'use client';

import { KeyRound } from 'lucide-react';
import type { ServiceView } from './types';

const NAME = /^[A-Za-z_][A-Za-z0-9_.-]*$/;

export const secretView: ServiceView = {
  name: 'secret',
  label: 'Secrets',
  description: 'Credentials the engine reads from its secret adapters (.env, Naas).',
  icon: KeyRound,
  group: 'Platform',
  noun: { one: 'secret', many: 'secrets' },
  entryIcon: () => KeyRound,
  level: () => ({
    columns: [
      {
        id: 'value',
        label: 'Value',
        width: 'minmax(120px, 0.5fr)',
        render: () => (
          <span className="data-masked-dots" aria-label="Hidden value">
            ••••••••••••
          </span>
        ),
      },
    ],
    emptyTitle: 'No secrets',
    emptyText: 'Create one to make it available to every module through the secret service.',
  }),
  facts: () => [{ label: 'Stored in', value: 'Every configured secret adapter' }],
  createLabel: 'New secret',
  editor: {
    language: () => 'plaintext',
    compact: true,
    secret: true,
    namePlaceholder: 'OPENAI_API_KEY',
    validateName: (name) =>
      NAME.test(name) ? null : 'Letters, digits, "_", "." and "-", not starting with a digit.',
  },
  deleteWarning: () =>
    'Removed from every configured secret adapter, including .env. Anything reading it fails until it is set again.',
  revealSeconds: 30,
};
