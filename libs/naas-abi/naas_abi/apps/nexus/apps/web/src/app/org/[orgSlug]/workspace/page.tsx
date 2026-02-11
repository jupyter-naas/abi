'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { authFetch } from '@/stores/auth';

/**
 * Org workspace landing page.
 * Fetches the user's workspaces within this organization
 * and redirects to the first available one.
 */
export default function OrgWorkspacePage() {
  const router = useRouter();
  const params = useParams();
  const orgSlug = params.orgSlug as string;
  const { isAuthenticated, token } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      router.replace(`/org/${orgSlug}/auth/login`);
      return;
    }

    // Fetch org workspaces and redirect to the first one
    const fetchAndRedirect = async () => {
      try {
        // First get the org by slug to get the org ID
        const brandingRes = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/organizations/slug/${orgSlug}/branding`
        );

        if (!brandingRes.ok) {
          setError('Organization not found');
          return;
        }

        // Fetch user's workspaces
        const wsRes = await authFetch('/api/workspaces/');
        if (!wsRes.ok) {
          setError('Failed to load workspaces');
          return;
        }

        const workspaces = await wsRes.json();

        // Filter workspaces by organization (if they have org_id)
        // For now, redirect to first workspace since org-workspace linking
        // may not be fully set up yet
        if (workspaces.length > 0) {
          router.replace(`/org/${orgSlug}/workspace/${workspaces[0].id}/chat`);
        } else {
          setError('No workspaces found');
        }
      } catch (err) {
        setError('Failed to load workspaces');
      }
    };

    fetchAndRedirect();
  }, [token, orgSlug, router]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center">
          <p className="text-lg font-medium text-destructive">{error}</p>
          <button
            onClick={() => router.push(`/org/${orgSlug}/auth/login`)}
            className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            Back to login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Loading workspaces...</p>
      </div>
    </div>
  );
}
