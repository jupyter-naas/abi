'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { 
  PanelLeft, 
  User, 
  Settings, 
  LogOut, 
  HelpCircle,
  GitBranch,
  ChevronDown,
  Check,
  Sparkles,
  Building2,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, type WorkspaceBranch, type Workspace } from '@/stores/workspace';
import { useAuthStore } from '@/stores/auth';

interface HeaderProps {
  title?: string;
  subtitle?: string;
}

export function Header({ title, subtitle }: HeaderProps = {}) {
  const [mounted, setMounted] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [branchMenuOpen, setBranchMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const branchMenuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { logout, user: authUser } = useAuthStore();
  
  const { 
    sidebarCollapsed, 
    toggleSidebar, 
    contextPanelOpen, 
    toggleContextPanel, 
    currentWorkspaceId,
    getCurrentBranch,
    getBranches,
    checkoutBranch,
  } = useWorkspaceStore();
  
  // Use authenticated user from auth store (not the hardcoded workspace store user)
  const user = authUser;

  // Helper to generate workspace-scoped URLs
  const getWorkspacePath = (path: string) => 
    currentWorkspaceId ? `/workspace/${currentWorkspaceId}${path}` : path;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
      if (branchMenuRef.current && !branchMenuRef.current.contains(event.target as Node)) {
        setBranchMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Use defaults on server to prevent hydration mismatch
  const sidebarOpen = mounted ? !sidebarCollapsed : true;
  const panelOpen = mounted ? contextPanelOpen : false;
  const displayUser = mounted ? user : null;
  
  // Git branch state
  const currentBranch = mounted ? getCurrentBranch() : null;
  const branches = mounted ? getBranches() : [];

  const handleCheckoutBranch = (branchId: string) => {
    checkoutBranch(branchId);
    setBranchMenuOpen(false);
  };

  const getBranchColor = (branch: WorkspaceBranch) => {
    if (branch.name === 'main') return 'text-green-500';
    if (branch.name === 'demo') return 'text-purple-500';
    if (branch.name === 'development') return 'text-blue-500';
    if (branch.name.startsWith('feature/')) return 'text-cyan-500';
    if (branch.name.startsWith('hotfix/')) return 'text-red-500';
    return 'text-muted-foreground';
  };


  return (
    <header className="glass-nav flex h-14 items-center justify-between border-b border-border/50 px-4">
      {/* Left side - show expand button when sidebar is collapsed */}
      <div className="flex items-center">
        {!sidebarOpen && (
          <button
            onClick={toggleSidebar}
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-md transition-all',
              'hover:bg-muted hover:text-foreground text-muted-foreground'
            )}
            title="Expand sidebar"
          >
            <PanelLeft size={16} />
          </button>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-1">
        {/* Branch Selector - Simple dropdown like Palantir */}
        <div ref={branchMenuRef} className="relative mr-2">
          <button
            onClick={() => setBranchMenuOpen(!branchMenuOpen)}
            className={cn(
              'flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors',
              'hover:bg-muted',
              branchMenuOpen && 'bg-muted border-primary'
            )}
          >
            <GitBranch size={14} className={currentBranch ? getBranchColor(currentBranch) : 'text-muted-foreground'} />
            <span className="font-medium">{currentBranch?.name || 'main'}</span>
            <ChevronDown size={14} className="text-muted-foreground" />
          </button>

          {branchMenuOpen && (
            <div className="glass-card absolute right-0 top-full z-50 mt-2 w-56 py-1">
              {branches.map((branch) => (
                <button
                  key={branch.id}
                  onClick={() => handleCheckoutBranch(branch.id)}
                  className={cn(
                    'flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors',
                    'hover:bg-primary/10',
                    currentBranch?.id === branch.id && 'bg-primary/5'
                  )}
                >
                  <GitBranch size={14} className={getBranchColor(branch)} />
                  <span className="flex-1 text-left">{branch.name}</span>
                  {currentBranch?.id === branch.id && (
                    <Check size={14} className="text-primary" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
        {/* Settings */}
        <Link
          href={getWorkspacePath('/settings')}
          className={cn(
            'flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-all',
            'hover:bg-muted hover:text-foreground'
          )}
          title="Settings"
        >
          <Settings size={16} />
        </Link>

        {/* AI Pane toggle */}
        <button
          onClick={toggleContextPanel}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-2 py-1.5 transition-all',
            'hover:bg-muted',
            panelOpen ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'
          )}
          title="Toggle AI Assistant (⌘K)"
        >
          <Sparkles size={16} />
          <kbd className="hidden rounded border bg-muted px-1 text-[10px] text-muted-foreground sm:inline">
            ⌘K
          </kbd>
        </button>

        {/* User avatar with dropdown */}
        <div ref={userMenuRef} className="relative ml-1">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-full overflow-hidden transition-opacity',
              'hover:opacity-90',
              displayUser?.avatar ? 'bg-transparent' : 'bg-primary text-primary-foreground'
            )}
          >
            {displayUser?.avatar ? (
              <img
                src={displayUser.avatar}
                alt={displayUser.name || 'User'}
                className="h-full w-full object-cover"
              />
            ) : (
              <span className="text-xs font-medium">{displayUser?.name?.charAt(0) || 'U'}</span>
            )}
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 top-full z-50 mt-2 min-w-56 w-64 rounded-lg border bg-card shadow-lg p-2">
              {/* User info */}
              <div className="border-b border-border/50 px-4 py-3">
                <p className="truncate font-medium" title={displayUser?.name || 'User'}>
                  {displayUser?.name || 'User'}
                </p>
                <p className="min-w-0 truncate text-xs text-muted-foreground" title={displayUser?.email || ''}>
                  {displayUser?.email || ''}
                </p>
              </div>

              {/* Menu items */}
              <div className="py-2">
                <Link
                  href="/account"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-3 rounded-md px-4 py-2.5 text-sm transition-colors hover:bg-muted"
                >
                  <User size={16} className="shrink-0 text-muted-foreground" />
                  Account Settings
                </Link>
                <Link
                  href={getWorkspacePath('/settings')}
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-3 rounded-md px-4 py-2.5 text-sm transition-colors hover:bg-muted"
                >
                  <Settings size={16} className="shrink-0 text-muted-foreground" />
                  Workspace Settings
                </Link>
                <Link
                  href="/organizations"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-3 rounded-md px-4 py-2.5 text-sm transition-colors hover:bg-muted"
                >
                  <Building2 size={16} className="shrink-0 text-muted-foreground" />
                  Organization Settings
                </Link>
                <Link
                  href={getWorkspacePath('/help')}
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-3 rounded-md px-4 py-2.5 text-sm transition-colors hover:bg-muted"
                >
                  <HelpCircle size={16} className="shrink-0 text-muted-foreground" />
                  Help
                </Link>
              </div>

              {/* Logout */}
              <div className="border-t border-border/50 py-2">
                <button
                  onClick={() => {
                    setUserMenuOpen(false);
                    logout();
                    router.push('/auth/login');
                  }}
                  className="flex w-full items-center gap-3 rounded-md px-4 py-2.5 text-sm text-destructive transition-colors hover:bg-destructive/10"
                >
                  <LogOut size={16} className="shrink-0" />
                  Log Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
