'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import Link from 'next/link';
import {
  ArrowLeft, Check, User, LogOut, HelpCircle, Building2,
} from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useFeature } from '@/hooks/use-feature';
import { useWorkspaceStore } from '@/stores/workspace';
import { isMobileChatThreadOpen, parseChatRoute } from '@/app/workspace/[workspaceId]/chat/lib/chat-route';
import { getWorkspacePath } from '../sidebar/utils';
import { WorkspaceMark } from '../workspace-mark';
import { useShellTitle } from '../shell-title';
import { resolveMobileTopBarTitle } from './mobile-top-bar-title';

type MobileTopBarProps = {
  /** Top-level tab chrome, or an immersive detail view (chat thread, file browser). */
  variant: 'top' | 'detail';
  /** Title for shell-owned views that mount no page Header (chat/files lists). */
  title?: string;
  /** Page-level actions for the current route, rendered on the right. */
  actions?: ReactNode;
  /** Override the default chat-list back target on detail views. */
  onDetailBack?: () => void;
  detailBackLabel?: string;
};

export function MobileTopBar({
  variant,
  title: titleOverride,
  actions,
  onDetailBack,
  detailBackLabel,
}: MobileTopBarProps) {
  const router = useRouter();
  const pathname = usePathname();
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
  const mobilePendingChatSlug = useWorkspaceStore((s) => s.mobilePendingChatSlug);
  const conversations = useWorkspaceStore((s) => s.conversations);
  const setActiveConversation = useWorkspaceStore((s) => s.setActiveConversation);
  const setMobilePendingChatSlug = useWorkspaceStore((s) => s.setMobilePendingChatSlug);

  const { logout, user } = useAuthStore();
  const canOrganizationSettings = useFeature('settings.organization');
  const { title: pageTitle } = useShellTitle();

  useEffect(() => setMounted(true), []);

  const currentWorkspace = mounted
    ? workspaces.find((w) => w.id === currentWorkspaceId) || null
    : null;

  const chatRoute = parseChatRoute(pathname);
  const isChatThread = isMobileChatThreadOpen(chatRoute, mobilePendingChatSlug);

  const threadTitle =
    conversations.find((c) => c.id === activeConversationId)?.title || 'New chat';

  const title = resolveMobileTopBarTitle({
    variant,
    titleOverride,
    pageTitle,
    threadTitle,
    workspaceName: currentWorkspace?.name,
    isChatThread,
  });

  // Replace rather than push: the list is where we came from, so stacking a
  // second entry would make hardware back bounce through the detail again.
  const handleBack = onDetailBack ?? (() => {
    setActiveConversation(null);
    setMobilePendingChatSlug(null);
    router.replace(getWorkspacePath(currentWorkspaceId, '/chat'));
  });

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
        {variant === 'detail' ? (
          <button
            type="button"
            onClick={handleBack}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center text-foreground hover:bg-muted"
            aria-label={detailBackLabel ?? 'Back to chats'}
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
            <WorkspaceMark
              name={currentWorkspace?.name}
              icon={currentWorkspace?.icon}
              logoUrl={currentWorkspace?.theme?.logoUrl}
              logoEmoji={currentWorkspace?.theme?.logoEmoji}
              fallbackLetter="Z"
              letterClassName="text-sm font-bold text-white"
            />
          </button>
        )}

        <h1 className="min-w-0 flex-1 truncate text-base font-semibold">{title}</h1>

        {actions}

        {/* Profile only on list / top-level tabs. Detail views stay immersive. */}
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
            <p className="px-3 py-1.5 text-micro font-semibold uppercase tracking-wider text-muted-foreground">
              Workspaces
            </p>
            {workspaces.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                onClick={() => {
                  setWorkspaceOpen(false);
                  setActiveConversation(null);
                  router.push(`/workspace/${workspace.id}/maps/presence`);
                }}
                className={cn(
                  'flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors',
                  'hover:bg-workspace-accent-10',
                  currentWorkspaceId === workspace.id && 'bg-workspace-accent-5'
                )}
              >
                <div
                  className="flex h-6 w-6 flex-shrink-0 items-center justify-center overflow-hidden"
                  style={{
                    backgroundColor: workspace.theme?.primaryColor || '#22c55e',
                    borderRadius: 0,
                  }}
                >
                  <WorkspaceMark
                    name={workspace.name}
                    icon={workspace.icon}
                    logoUrl={workspace.theme?.logoUrl}
                    logoEmoji={workspace.theme?.logoEmoji}
                    letterClassName="text-xs text-white"
                  />
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
                href="/account/profile"
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
