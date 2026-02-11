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
  CreditCard,
} from 'lucide-react';
import { Header } from '@/components/shell/header';

const orgSettingsNav = [
  { href: '/organization', label: 'General', icon: Building2 },
  { href: '/organization/workspaces', label: 'Workspaces', icon: FolderKanban },
  { href: '/organization/branding', label: 'Branding', icon: Paintbrush },
  { href: '/organization/admins', label: 'Admins', icon: Users },
  { href: '/organization/domains', label: 'Domains', icon: Globe },
  { href: '/organization/billing', label: 'Billing', icon: CreditCard },
];

function NavItem({
  item,
  pathname,
  workspaceId,
}: {
  item: typeof orgSettingsNav[0];
  pathname: string;
  workspaceId: string;
}) {
  const fullHref = `/workspace/${workspaceId}${item.href}`;
  const isActive = pathname === fullHref || pathname.endsWith(item.href);
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

export default function OrganizationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const params = useParams();
  const workspaceId = params.workspaceId as string;

  return (
    <div className="flex h-full flex-col">
      <Header
        title="Organization Settings"
        subtitle=""
      />

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
                workspaceId={workspaceId}
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
