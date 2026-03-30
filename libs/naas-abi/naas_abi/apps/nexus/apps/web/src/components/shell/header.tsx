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
  Plus,
  RefreshCw,
  AlertCircle,
  Search,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAuthStore } from '@/stores/auth';
import { useGit } from '@/hooks/use-git';
import { FilePalette } from './file-palette';

interface HeaderProps {
  title?: string;
  subtitle?: string;
}

export function Header({ title, subtitle }: HeaderProps = {}) {
  const [mounted, setMounted] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [branchMenuOpen, setBranchMenuOpen] = useState(false);
  const [newBranchName, setNewBranchName] = useState('');
  const [creatingBranch, setCreatingBranch] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
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
  } = useWorkspaceStore();

  // Real git state
  const { branches, status, currentBranch, totalChanges, loading: gitLoading, refresh: gitRefresh, checkout } = useGit();
  
  // Use authenticated user from auth store
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

    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'p') {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  // Use defaults on server to prevent hydration mismatch
  const sidebarOpen = mounted ? !sidebarCollapsed : true;
  const panelOpen = mounted ? contextPanelOpen : false;
  const displayUser = mounted ? user : null;
  
  const handleCheckout = async (name: string) => {
    await checkout(name);
    setBranchMenuOpen(false);
    setNewBranchName('');
    setCreatingBranch(false);
  };

  const handleCreateBranch = async () => {
    if (!newBranchName.trim()) return;
    await checkout(newBranchName.trim(), true);
    setBranchMenuOpen(false);
    setNewBranchName('');
    setCreatingBranch(false);
  };

  const branchColor = (name: string) => {
    if (name === 'main' || name === 'master') return 'text-green-500';
    if (name === 'demo') return 'text-purple-500';
    if (name === 'development' || name === 'dev') return 'text-blue-500';
    if (name.startsWith('feature/')) return 'text-cyan-500';
    if (name.startsWith('hotfix/')) return 'text-red-500';
    return 'text-muted-foreground';
  };


  return (
    <>
      <FilePalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />

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

        {/* Center — file search trigger (VS Code Cmd+P style) */}
        <button
          onClick={() => setPaletteOpen(true)}
          className={cn(
            'flex items-center gap-2 rounded-lg border border-border/60 bg-muted/40 px-3 py-1.5',
            'text-sm text-muted-foreground transition-all',
            'hover:border-border hover:bg-muted hover:text-foreground',
            'w-56 sm:w-72 md:w-80'
          )}
        >
          <Search size={13} className="shrink-0" />
          <span className="flex-1 text-left text-xs">Go to file…</span>
          <kbd className="hidden rounded border bg-background px-1.5 py-0.5 text-[10px] sm:inline">
            ⌘P
          </kbd>
        </button>

      {/* Right side */}
      <div className="flex items-center gap-1">
        {/* Branch Selector — wired to real ~/aia git repo */}
        <div ref={branchMenuRef} className="relative mr-2">
          <button
            onClick={() => setBranchMenuOpen(!branchMenuOpen)}
            className={cn(
              'flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors',
              'hover:bg-muted',
              branchMenuOpen && 'bg-muted border-primary'
            )}
          >
            <GitBranch size={14} className={branchColor(currentBranch?.name ?? 'main')} />
            <span className="font-medium">{currentBranch?.name ?? (gitLoading ? '…' : 'main')}</span>
            {totalChanges > 0 && (
              <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-amber-500/20 px-1 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                {totalChanges}
              </span>
            )}
            <ChevronDown size={14} className="text-muted-foreground" />
          </button>

          {branchMenuOpen && (
            <div className="glass-card absolute right-0 top-full z-50 mt-2 w-64 py-1">
              {/* Status summary */}
              {status && (status.staged.length > 0 || status.changed.length > 0 || status.untracked.length > 0) && (
                <div className="border-b border-border/50 px-3 py-2 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5 font-medium text-amber-600 dark:text-amber-400">
                    <AlertCircle size={11} />
                    {status.staged.length > 0 && <span>{status.staged.length} staged</span>}
                    {status.changed.length > 0 && <span>{status.changed.length} changed</span>}
                    {status.untracked.length > 0 && <span>{status.untracked.length} untracked</span>}
                  </div>
                  {status.ahead > 0 && (
                    <span className="mt-0.5 block text-blue-500">↑ {status.ahead} ahead of origin</span>
                  )}
                  {status.behind > 0 && (
                    <span className="mt-0.5 block text-orange-500">↓ {status.behind} behind origin</span>
                  )}
                </div>
              )}

              {/* Branch list */}
              <div className="max-h-48 overflow-y-auto py-1">
                {branches.map((branch) => (
                  <button
                    key={branch.name}
                    onClick={() => handleCheckout(branch.name)}
                    className={cn(
                      'flex w-full items-center gap-2 px-3 py-1.5 text-sm transition-colors',
                      'hover:bg-primary/10',
                      branch.current && 'bg-primary/5'
                    )}
                  >
                    <GitBranch size={13} className={branchColor(branch.name)} />
                    <span className="flex-1 text-left">{branch.name}</span>
                    {branch.ahead > 0 && (
                      <span className="text-[10px] text-blue-500">↑{branch.ahead}</span>
                    )}
                    {branch.behind > 0 && (
                      <span className="text-[10px] text-orange-500">↓{branch.behind}</span>
                    )}
                    {branch.current && <Check size={13} className="text-primary" />}
                  </button>
                ))}
              </div>

              {/* New branch */}
              <div className="border-t border-border/50 px-3 py-2">
                {creatingBranch ? (
                  <div className="flex items-center gap-1.5">
                    <input
                      autoFocus
                      type="text"
                      value={newBranchName}
                      onChange={(e) => setNewBranchName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleCreateBranch();
                        if (e.key === 'Escape') { setCreatingBranch(false); setNewBranchName(''); }
                      }}
                      placeholder="new-branch-name"
                      className="flex-1 rounded border bg-background px-2 py-1 text-xs outline-none ring-1 ring-primary"
                    />
                    <button onClick={handleCreateBranch} className="text-xs text-primary hover:underline">Create</button>
                  </div>
                ) : (
                  <button
                    onClick={() => setCreatingBranch(true)}
                    className="flex w-full items-center gap-2 rounded-md px-1 py-1 text-xs text-muted-foreground hover:text-foreground"
                  >
                    <Plus size={12} />
                    New branch
                  </button>
                )}
              </div>

              {/* Refresh */}
              <div className="border-t border-border/50 px-3 py-1.5">
                <button
                  onClick={() => { gitRefresh(); }}
                  className="flex w-full items-center gap-2 px-1 py-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  <RefreshCw size={11} className={gitLoading ? 'animate-spin' : ''} />
                  Refresh
                </button>
              </div>
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
    </>
  );
}
