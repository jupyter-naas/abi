'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import Link from 'next/link';
import {
  ArrowLeft, Check, User, LogOut, HelpCircle, Building2,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useTypographyPilot } from '@/hooks/use-typography-pilot';
import { microTextClass } from '@/lib/typography-pilot';
import { useAuthStore } from '@/stores/auth';
import { useFeature } from '@/hooks/use-feature';
import { useWorkspaceStore } from '@/stores/workspace';
import { getWorkspacePath } from '../sidebar/utils';
import { useShellTitle } from '../shell-title';

type MobileTopBarProps = {
  /** Chat thread stack: back + title + profile (no workspace mark). */
  variant: 'top' | 'thread';
  /** Title for shell-owned views that mount no page Header (the chat list). */
  title?: string;
  /** Page-level actions for the current route, rendered on the right. */
  actions?: ReactNode;
};

export function MobileTopBar({ variant, title: titleOverride, actions }: MobileTopBarProps) {
  const typographyPilot = useTypographyPilot();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [workspacePos, setWorkspacePos] = useState({ top: 0, left: 0 });
  const [profilePos, setProfilePos] = useState({ top: 0, right: 0 });
  const workspaceBtnRef = useRef<HTMLButtonElement>(null);
  const profileBtnRef = useRef<HTMLButtonElement>(null);

  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const activeConversationId = useWorkspaceStore((s) => s.activeConversationId);
  const conversations = useWorkspaceStore((s) => s.conversations);
  const setActiveConversation = useWorkspaceStore((s) => s.setActiveConversation);

  const { logout, user } = useAuthStore();
  const canOrganizationSettings = useFeature('settings.organization');
  const { title: pageTitle } = useShellTitle();

  useEffect(() => setMounted(true), []);

  const currentWorkspace = mounted
    ? workspaces.find((w) => w.id === currentWorkspaceId) || null
    : null;

  const threadTitle =
    conversations.find((c) => c.id === activeConversationId)?.title || 'New chat';

  const title =
    variant === 'thread'
      ? threadTitle
      : titleOverride ?? pageTitle ?? currentWorkspace?.name ?? '';

  // Replace rather than push: the list is where we came from, so stacking a
  // second entry would make hardware back bounce through the thread again.
  const handleBack = () => {
    setActiveConversation(null);
    router.replace(getWorkspacePath(currentWorkspaceId, '/chat'));
  };

  const openWorkspaceMenu = () => {
    if (!workspaceBtnRef.current) return;
    const rect = workspaceBtnRef.current.getBoundingClientRect();
    setWorkspacePos({ top: rect.bottom + 6, left: Math.max(8, rect.left) });
    setProfileOpen(false);
    setWorkspaceOpen(true);
  };

  const openProfileMenu = () => {
    if (!profileBtnRef.current) return;
    const rect = profileBtnRef.current.getBoundingClientRect();
    setProfilePos({ top: rect.bottom + 6, right: Math.max(8, window.innerWidth - rect.right) });
    setWorkspaceOpen(false);
    setProfileOpen(true);
  };

  return (
    <>
      {/* min-h, not h: the safe-area inset is padding inside the box, so a fixed
          height would swallow the row on notched devices in standalone mode. */}
      <header
        className="flex min-h-12 flex-shrink-0 items-center gap-2 border-b border-border/60 px-2"
        style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}
      >
        {variant === 'thread' ? (
          <button
            type="button"
            onClick={handleBack}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center text-foreground hover:bg-muted"
            aria-label="Back to chats"
          >
            <ArrowLeft size={20} />
          </button>
        ) : (
          <button
            ref={workspaceBtnRef}
            type="button"
            onClick={openWorkspaceMenu}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden transition-all hover:ring-2 hover:ring-workspace-accent/50"
            style={{ backgroundColor: currentWorkspace?.theme?.primaryColor || '#22c55e' }}
            title={currentWorkspace?.name || 'Workspace'}
            aria-label="Switch workspace"
          >
            {currentWorkspace?.theme?.logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={currentWorkspace.theme.logoUrl}
                alt={currentWorkspace.name}
                className="h-full w-full object-cover"
              />
            ) : (
              <span className="text-sm font-bold text-white">
                {currentWorkspace?.theme?.logoEmoji
                  || currentWorkspace?.icon
                  || currentWorkspace?.name?.charAt(0)
                  || 'Z'}
              </span>
            )}
          </button>
        )}

        <h1 className={cn('shell-mobile-title min-w-0 flex-1 truncate text-sm font-semibold')}>{title}</h1>

        {actions}

        {/* Profile only on list / top-level tabs. Thread stays immersive (back + title). */}
        {variant === 'top' && (
          <button
            ref={profileBtnRef}
            type="button"
            onClick={openProfileMenu}
            className={cn(
              // Profile stays circular (same as desktop). Other mobile chrome stays sharp.
              'flex h-8 w-8 flex-shrink-0 items-center justify-center overflow-hidden rounded-full',
              user?.avatar ? 'bg-transparent' : 'bg-primary text-primary-foreground'
            )}
            aria-label="Account menu"
          >
            {user?.avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={user.avatar} alt={user.name || 'User'} className="h-full w-full object-cover" />
            ) : (
              <span className="text-xs font-medium">{user?.name?.charAt(0) || 'U'}</span>
            )}
          </button>
        )}
      </header>

      {workspaceOpen && mounted && createPortal(
        // Portals land outside the shell, so re-declare org branding to keep
        // the radius token applying to menu chrome.
        <div data-org-branded="true">
          <div className="fixed inset-0 z-[299]" onClick={() => setWorkspaceOpen(false)} />
          <div
            className="glass-card fixed z-[300] w-64 py-1 shadow-lg"
            style={{ top: workspacePos.top, left: workspacePos.left }}
          >
            <p className={cn('px-3 py-1.5 font-semibold uppercase tracking-wider text-muted-foreground', microTextClass(typographyPilot))}>
              Workspaces
            </p>
            {workspaces.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                onClick={() => {
                  setWorkspaceOpen(false);
                  setActiveConversation(null);
                  router.push(`/workspace/${workspace.id}/chat`);
                }}
                className={cn(
                  'flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors',
                  'hover:bg-workspace-accent-10',
                  currentWorkspaceId === workspace.id && 'bg-workspace-accent-5'
                )}
              >
                <div
                  className="flex h-6 w-6 flex-shrink-0 items-center justify-center overflow-hidden"
                  style={{ backgroundColor: workspace.theme?.primaryColor || '#22c55e' }}
                >
                  {workspace.theme?.logoUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={workspace.theme.logoUrl} alt={workspace.name} className="h-full w-full object-cover" />
                  ) : (
                    <span className="text-xs text-white">
                      {workspace.theme?.logoEmoji || workspace.icon || workspace.name.charAt(0)}
                    </span>
                  )}
                </div>
                <span className="flex-1 text-left font-medium">{workspace.name}</span>
                {currentWorkspaceId === workspace.id && (
                  <Check size={14} className="text-workspace-accent" />
                )}
              </button>
            ))}
          </div>
        </div>,
        document.body
      )}

      {profileOpen && mounted && createPortal(
        <div data-org-branded="true">
          <div className="fixed inset-0 z-[299]" onClick={() => setProfileOpen(false)} />
          <div
            className="fixed z-[300] w-64 border bg-card p-2 shadow-lg"
            style={{ top: profilePos.top, right: profilePos.right }}
          >
            <div className="border-b border-border/50 px-4 py-3">
              <p className="truncate font-medium">{user?.name || 'User'}</p>
              <p className="truncate text-xs text-muted-foreground">{user?.email || ''}</p>
            </div>
            <div className="py-2">
              <Link
                href="/account"
                onClick={() => setProfileOpen(false)}
                className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-muted"
              >
                <User size={16} className="shrink-0 text-muted-foreground" />
                Account Settings
              </Link>
              {canOrganizationSettings && (
                <Link
                  href="/organizations"
                  onClick={() => setProfileOpen(false)}
                  className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-muted"
                >
                  <Building2 size={16} className="shrink-0 text-muted-foreground" />
                  Organization Settings
                </Link>
              )}
              <Link
                href={getWorkspacePath(currentWorkspaceId, '/help')}
                onClick={() => setProfileOpen(false)}
                className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-muted"
              >
                <HelpCircle size={16} className="shrink-0 text-muted-foreground" />
                Help
              </Link>
            </div>
            <div className="border-t border-border/50 py-2">
              <button
                type="button"
                onClick={() => {
                  setProfileOpen(false);
                  logout();
                  router.push('/auth/login');
                }}
                className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-destructive hover:bg-destructive/10"
              >
                <LogOut size={16} className="shrink-0" />
                Log Out
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
