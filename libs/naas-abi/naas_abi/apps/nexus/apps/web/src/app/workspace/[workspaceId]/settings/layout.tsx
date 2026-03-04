'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  Download,
  Cpu,
  Users,
  Bot,
  Brush,
  Shield,
  Server,
} from 'lucide-react';
import { useWorkspaceStore } from '@/stores/workspace';
import { Header } from '@/components/shell/header';

// Workspace-specific settings (accessed via gear icon)
const workspaceSettingsNav = [
  { href: '/settings/secrets', label: 'Secrets', icon: Shield },
  { href: '/settings/servers', label: 'Servers', icon: Server },
  { href: '/settings/models', label: 'Models', icon: Cpu },
  { href: '/settings/agents', label: 'Agents', icon: Bot },
  { href: '/settings/theme', label: 'Theme', icon: Brush },
  { href: '/settings/members', label: 'Members', icon: Users },
  { href: '/settings/export', label: 'Data Export', icon: Download },
];

function NavItem({ item, pathname, workspaceId }: { item: typeof workspaceSettingsNav[0]; pathname: string; workspaceId: string | null }) {
  const fullHref = workspaceId ? `/workspace/${workspaceId}${item.href}` : item.href;
  const isActive = pathname === fullHref || pathname.endsWith(item.href);
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={fullHref}
        className={cn(
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          isActive
            ? 'bg-workspace-accent-10 text-workspace-accent'
            : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
        )}
      >
        <Icon size={18} />
        {item.label}
      </Link>
    </li>
  );
}

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  
  // Get current workspace for the header
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);

  return (
    <div className="flex h-full flex-col">
      <Header 
        title="Workspace Settings" 
        subtitle={currentWorkspace?.name || 'Configure your workspace'}
      />
      
      <div className="flex flex-1 overflow-hidden">
        {/* Settings sidebar */}
        <nav className="w-56 flex-shrink-0 border-r bg-card/50 p-4 overflow-y-auto">
          <h2 className="mb-3 px-3 text-sm font-semibold text-foreground">
            Workspace Settings
          </h2>
          <div className="mb-4 border-b border-border/50" />
          <ul className="space-y-1">
            {workspaceSettingsNav.map((item) => (
              <NavItem key={item.href} item={item} pathname={pathname} workspaceId={currentWorkspaceId} />
            ))}
          </ul>
        </nav>

        {/* Settings content */}
        <div className="flex-1 overflow-auto px-4 py-6">
          {children}
        </div>
      </div>
    </div>
  );
}
