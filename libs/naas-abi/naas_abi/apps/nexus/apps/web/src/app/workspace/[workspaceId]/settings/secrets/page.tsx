'use client';

import { SecretsPanel } from '@/components/settings/secrets-panel';
import { PrivateGate } from '@/components/view-as/private-to-person';

export default function SecretsPage() {
  // The workspace's secrets stay private in a view: nothing is asked for.
  return (
    <PrivateGate what="The workspace's secrets">
      <SecretsPanel />
    </PrivateGate>
  );
}
