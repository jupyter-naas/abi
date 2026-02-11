'use client';

import { useState, useEffect } from 'react';
import { Plus, FolderKanban, Settings, Users, BarChart3 } from 'lucide-react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';

interface OrgWorkspace {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  organization_id: string;
  created_at: string;
  updated_at: string;
  // Branding from API
  logo_url?: string | null;
  logo_emoji?: string | null;
  organization_logo_url?: string | null;
  organization_logo_rectangle_url?: string | null;
}

export default function OrganizationWorkspacesPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  
  const [workspaces, setWorkspaces] = useState<OrgWorkspace[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchWorkspaces = async () => {
      if (!orgId) return;
      try {
        const { authFetch } = await import('@/stores/auth');
        const response = await authFetch(`/api/organizations/${orgId}/workspaces`);
        if (response.ok) {
          const data: OrgWorkspace[] = await response.json();
          setWorkspaces(data);
        } else {
          console.error('Failed to fetch workspaces:', response.status);
        }
      } catch (error) {
        console.error('Failed to fetch org workspaces:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchWorkspaces();
  }, [orgId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading workspaces...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Workspaces</h2>
          <p className="text-sm text-muted-foreground">
            Manage workspaces belonging to this organization
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 transition-colors">
          <Plus size={16} />
          Create Workspace
        </button>
      </div>

      {workspaces.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-card p-12 text-center">
          <FolderKanban size={48} className="mx-auto mb-4 text-muted-foreground" />
          <h3 className="mb-2 text-lg font-semibold">No workspaces yet</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Create your first workspace to get started
          </p>
          <button className="inline-flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 transition-colors">
            <Plus size={16} />
            Create Workspace
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {workspaces.map((workspace) => {
            const API_BASE = getApiUrl();
            const normalize = (url?: string | null) => (url && url.startsWith('/') ? `${API_BASE}${url}` : url || undefined);
            const logo = normalize(workspace.logo_url) 
              || normalize(workspace.organization_logo_url)
              || normalize(workspace.organization_logo_rectangle_url);
            return (
            <div
              key={workspace.id}
              className="group rounded-xl border bg-card p-6 transition-all hover:border-blue-500/50 hover:shadow-md"
            >
              <div className="mb-4 flex items-start justify-between">
                {logo ? (
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-transparent">
                    <img src={logo} alt={workspace.name} className="h-12 w-12 rounded-xl object-contain" />
                  </div>
                ) : (
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl text-2xl" style={{ backgroundColor: '#22c55e20' }}>
                    📁
                  </div>
                )}
                <button className="opacity-0 transition-opacity group-hover:opacity-100 rounded-lg p-1 hover:bg-muted">
                  <Settings size={16} className="text-muted-foreground" />
                </button>
              </div>

              <h3 className="mb-1 font-semibold">{workspace.name}</h3>
              <p className="mb-4 text-xs text-muted-foreground">
                /{workspace.slug}
              </p>

              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                  <Users size={14} />
                  <span>5</span>
                </div>
                <div className="flex items-center gap-1">
                  <BarChart3 size={14} />
                  <span>24</span>
                </div>
              </div>

              <div className="mt-4 flex gap-2">
                <Link
                  href={`/workspace/${workspace.id}/chat`}
                  className="flex-1 rounded-lg border px-3 py-2 text-center text-xs font-medium transition-colors hover:bg-muted"
                >
                  Open
                </Link>
                <Link
                  href={`/workspace/${workspace.id}/settings`}
                  className="flex-1 rounded-lg border px-3 py-2 text-center text-xs font-medium transition-colors hover:bg-muted"
                >
                  Settings
                </Link>
              </div>
            </div>
            );
          })}
        </div>
      )}

      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <p className="text-sm text-muted-foreground">
          Workspaces inherit branding from the organization but can customize their own themes.
        </p>
      </div>
    </div>
  );
}
