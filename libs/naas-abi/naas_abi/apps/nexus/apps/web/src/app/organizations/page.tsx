'use client';

import { useEffect, useState } from 'react';
import { Building2, ArrowRight, ArrowLeft } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useOrganizationStore } from '@/stores/organization';

export default function OrganizationsPage() {
  const router = useRouter();
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const { organizations, fetchOrganizations } = useOrganizationStore();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { await fetchOrganizations(); } finally { setLoading(false); }
    })();
  }, [fetchOrganizations]);

  const handleCancel = () => {
    if (currentWorkspaceId) {
      router.push(`/workspace/${currentWorkspaceId}/chat`);
    } else {
      router.push('/');
    }
  };

  // Show loading state
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Loading organizations...</p>
      </div>
    );
  }

  // If user has only one org, redirect directly to its settings
  if (organizations.length === 1) {
    router.push(`/organizations/${organizations[0].id}/settings`);
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Redirecting...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      {/* Compact Header - matching workspace navbar height */}
      <header className="flex h-14 items-center border-b bg-card/50 px-4">
        <button
          onClick={handleCancel}
          className="mr-3 flex items-center justify-center rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Back to workspace"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="text-base font-semibold">Organizations</h1>
          <p className="text-xs text-muted-foreground">
            Select an organization to manage
          </p>
        </div>
      </header>

      {/* Organizations Grid - compact boxes */}
      <main className="flex-1 p-6">
        {organizations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <Building2 size={48} className="mb-3 text-muted-foreground opacity-50" />
            <h2 className="mb-1 text-base font-semibold">No organizations found</h2>
            <p className="text-sm text-muted-foreground">
              You don't have access to any organizations yet.
            </p>
          </div>
        ) : (
          <div className="mx-auto max-w-5xl">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {organizations.map((org) => {
                const logo = org.logoUrl || (org as any).logoRectangleUrl;
                const bg = org.primaryColor ? `${org.primaryColor}20` : '#22c55e20';
                return (
                <button
                  key={org.id}
                  onClick={() => router.push(`/organizations/${org.id}/settings`)}
                  className={cn(
                    'group flex items-center gap-3 rounded-lg border bg-card p-4 text-left transition-all',
                    'hover:border-primary/50 hover:bg-muted/50'
                  )}
                >
                  {/* Logo - compact */}
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-xl overflow-hidden"
                    style={{ backgroundColor: bg }}
                  >
                    {logo ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={logo} alt={org.name} className="h-full w-full object-contain p-1" />
                    ) : (
                      <span>{org.logoEmoji || '🏢'}</span>
                    )}
                  </div>

                  {/* Info */}
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-medium">{org.name}</h3>
                    <p className="truncate text-xs text-muted-foreground">/{org.slug}</p>
                  </div>

                  {/* Arrow */}
                  <ArrowRight
                    size={16}
                    className="shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
                  />
                </button>
              );})}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
