'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  User,
  Palette,
  ArrowLeft,
} from 'lucide-react';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAuthStore } from '@/stores/auth';

// User account settings (global, not workspace-scoped)
const accountSettingsNav = [
  { href: '/account', label: 'Profile', icon: User },
  { href: '/account/appearance', label: 'Appearance', icon: Palette },
  // Deactivated (not implemented yet):
  // { href: '/account/api-keys', label: 'API Keys', icon: Key },
  // { href: '/account/notifications', label: 'Notifications', icon: Bell },
  // { href: '/account/security', label: 'Security', icon: Shield },
];

function NavItem({ 
  item, 
  pathname 
}: { 
  item: typeof accountSettingsNav[0]; 
  pathname: string; 
}) {
  const isActive = pathname === item.href;
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={item.href}
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

export default function AccountLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const user = useAuthStore((state) => state.user);

  const handleBack = () => {
    if (currentWorkspaceId) {
      router.push(`/workspace/${currentWorkspaceId}/chat`);
    } else {
      router.push('/');
    }
  };

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header with back button and user name */}
      <header className="flex h-14 items-center border-b bg-card/50 px-4">
        <button
          onClick={handleBack}
          className="mr-3 flex items-center justify-center rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="text-sm font-semibold">{user?.name || 'Account'}</h1>
        </div>
      </header>
      
      <div className="flex flex-1 overflow-hidden">
        {/* Settings sidebar */}
        <nav className="w-56 flex-shrink-0 border-r bg-card/50 p-4 overflow-y-auto">
          <h2 className="mb-3 px-3 text-sm font-semibold text-foreground">
            Account Settings
          </h2>
          <div className="mb-4 border-b border-border/50" />
          <ul className="space-y-1">
            {accountSettingsNav.map((item) => (
              <NavItem key={item.href} item={item} pathname={pathname} />
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
