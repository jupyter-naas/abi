'use client';

import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import { ModelSets } from './model-sets';

/** Platform settings › Models: the model sets (who chats with which model directly). */
export default function PlatformModelsPage() {
  const [nonce, setNonce] = useState(0);
  return (
    <div className="access-settings-page">
      <OrgSettingsPageHeader
        title="Models"
        subtitle="Which models people chat with directly, by level. An agent's own model is always allowed."
        actions={
          <button
            type="button"
            className="org-settings-users-secondary-button"
            data-action="refresh"
            onClick={() => setNonce((n) => n + 1)}
            title="Refresh"
            aria-label="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        }
      />
      <ModelSets nonce={nonce} />
    </div>
  );
}
