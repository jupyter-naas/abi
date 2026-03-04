'use client';

import { Globe, Plus, CheckCircle2 } from 'lucide-react';

export default function OrgDomainsPage() {
  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Domains</h2>
          <p className="text-sm text-muted-foreground">
            Manage custom domains for your organization
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 transition-colors">
          <Plus size={16} />
          Add Domain
        </button>
      </div>

      <div className="rounded-xl border bg-card p-6">
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted mb-4">
            <Globe size={24} className="text-muted-foreground" />
          </div>
          <h3 className="text-sm font-medium mb-1">No custom domains configured</h3>
          <p className="text-xs text-muted-foreground max-w-sm">
            Add a custom domain to use your own URL for the login page instead of nexus.app/org/your-slug/auth/login
          </p>
        </div>
      </div>

      <p className="text-center text-xs text-muted-foreground">
        Custom domain management coming soon
      </p>
    </div>
  );
}
