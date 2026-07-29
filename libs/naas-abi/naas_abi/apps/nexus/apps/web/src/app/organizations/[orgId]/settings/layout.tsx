'use client';

import Link from 'next/link';
import { usePathname, useParams } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  Building2,
  Paintbrush,
  Users,
  Globe,
  FolderKanban,
  ArrowLeft,
  CreditCard,
} from 'lucide-react';
import { useEffect, useState } from 'react';

const orgSettingsNav = [
  { href: '/settings', label: 'General', icon: Building2 },
  { href: '/settings/workspaces', label: 'Workspaces', icon: FolderKanban },
  { href: '/settings/branding', label: 'Branding', icon: Paintbrush },
  { href: '/settings/admins', label: 'Admins', icon: Users },
  { href: '/settings/domains', label: 'Domains', icon: Globe },
  { href: '/settings/billing', label: 'Billing', icon: CreditCard },
];

function NavItem({
  item,
  pathname,
  orgId,
}: {
  item: typeof orgSettingsNav[0];
  pathname: string;
  orgId: string;
}) {
  const fullHref = `/organizations/${orgId}${item.href}`;
  const isActive = pathname === fullHref;
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={fullHref}
        className={cn(
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          isActive
            ? 'bg-blue-500/10 text-blue-500'
            : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
        )}
      >
        <Icon size={18} />
        {item.label}
      </Link>
    </li>
  );
}

export default function OrganizationSettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const params = useParams();
  const orgId = params.orgId as string;
  const [orgName, setOrgName] = useState('');
  const [borderRadius, setBorderRadius] = useState('0');
  const [key, setKey] = useState(0); // Force re-render
  const [orgCount, setOrgCount] = useState<number | null>(null);

  useEffect(() => {
    const fetchOrg = async () => {
      try {
        const { authFetch } = await import('@/stores/auth');
        
        // Fetch current org details
        const response = await authFetch(`/api/organizations/${orgId}`);
        if (response.ok) {
          const data = await response.json();
          setOrgName(data.name);
          // Handle border radius - allow 0, only fallback if undefined/null
          const radius = data.loginBorderRadius ?? data.login_border_radius ?? '0';
          console.log('[Org Layout] Fetched border radius:', radius, '(type:', typeof radius, ') from org:', data.name);
          console.log('[Org Layout] Raw org data:', { loginBorderRadius: data.loginBorderRadius, login_border_radius: data.login_border_radius });
          setBorderRadius(radius);
        }
        
        // Fetch all orgs to determine if user has multiple
        const orgsResponse = await authFetch('/api/organizations/');
        if (orgsResponse.ok) {
          const orgs = await orgsResponse.json();
          setOrgCount(orgs.length);
        }
      } catch (error) {
        console.error('Failed to fetch organization:', error);
      }
    };

    if (orgId) {
      fetchOrg();
    }

    // Listen for branding updates
    const handleBrandingUpdate = () => {
      console.log('[Org Layout] Branding updated event received, refetching...');
      fetchOrg();
      setKey(prev => prev + 1);
    };

    window.addEventListener('org-branding-updated', handleBrandingUpdate);
    return () => window.removeEventListener('org-branding-updated', handleBrandingUpdate);
  }, [orgId]);

  console.log('[Org Layout] Rendering with border radius:', borderRadius, 'px');

  // Determine where "back" should go
  // If user has only 1 org, go back to their current workspace
  // If user has multiple orgs, go to the organizations list
  const getBackHref = () => {
    if (orgCount === 1) {
      // Single org - go back to workspace
      const { useWorkspaceStore } = require('@/stores/workspace');
      const currentWorkspaceId = useWorkspaceStore.getState().currentWorkspaceId;
      return currentWorkspaceId ? `/workspace/${currentWorkspaceId}/chat` : '/';
    }
    // Multiple orgs - go to org picker
    return '/organizations';
  };

  return (
    <div 
      className="flex h-screen flex-col bg-background"
      data-org-branded="true"
      style={{
        '--org-border-radius': `${borderRadius}px`,
      } as React.CSSProperties}
      key={key}
    >
      {/* Compact Header - just org name and back button */}
      <header className="flex h-14 items-center border-b bg-card/50 px-4">
        <Link
          href={getBackHref()}
          className="mr-3 flex items-center justify-center rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title={orgCount === 1 ? "Back to workspace" : "Back to organizations"}
        >
          <ArrowLeft size={20} />
        </Link>
        {orgName && (
          <div className="flex items-center gap-2">
            <Building2 size={16} className="text-muted-foreground" />
            <span className="text-sm font-medium">{orgName}</span>
          </div>
        )}
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Settings sidebar */}
        <nav className="w-56 flex-shrink-0 border-r bg-card/50 p-4 overflow-y-auto">
          <h2 className="mb-3 px-3 text-sm font-semibold text-foreground">
            Organization Settings
          </h2>
          <div className="mb-4 border-b border-border/50" />
          <ul className="space-y-1">
            {orgSettingsNav.map((item) => (
              <NavItem
                key={item.href}
                item={item}
                pathname={pathname}
                orgId={orgId}
              />
            ))}
          </ul>
        </nav>

        {/* Settings content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="mx-auto max-w-4xl">{children}</div>
        </div>
      </div>
    </div>
  );
}
