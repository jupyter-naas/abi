'use client';

import { PrivateGate } from '@/components/view-as/private-to-person';
import ApiKeysPage from './api-keys';

export default function Page() {
  // The person's API keys stay private in a view: nothing is asked for.
  return (
    <PrivateGate what="API keys">
      <ApiKeysPage />
    </PrivateGate>
  );
}
