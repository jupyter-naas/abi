'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import {
  ArrowLeft, X,
} from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { isMobileChatThreadOpen, parseChatRoute } from '@/app/workspace/[workspaceId]/chat/lib/chat-route';
import { getWorkspacePath } from '../sidebar/utils';
import { WorkspaceMark, WorkspaceMarkFrame } from '../workspace-mark';
import { WorkspacesSection } from '../sidebar/workspaces-section';
import { useShellTitle } from '../shell-title';
import { resolveMobileTopBarTitle } from './mobile-top-bar-title';
import { AccountMenuPanel, UserAvatar } from '../account-menu';

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
  const [profilePos, setProfilePos] = useState({ top: 0, right: 0 });
  const profileBtnRef = useRef<HTMLButtonElement>(null);

  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const activeConversationId = useWorkspaceStore((s) => s.activeConversationId);
  const mobilePendingChatSlug = useWorkspaceStore((s) => s.mobilePendingChatSlug);
  const conversations = useWorkspaceStore((s) => s.conversations);
  const setActiveConversation = useWorkspaceStore((s) => s.setActiveConversation);
  const setMobilePendingChatSlug = useWorkspaceStore((s) => s.setMobilePendingChatSlug);

  const user = useAuthStore((s) => s.user);
  const { title: pageTitle } = useShellTitle();

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!workspaceOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setWorkspaceOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [workspaceOpen]);

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

  const openWorkspaceSheet = () => {
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
            type="button"
            onClick={openWorkspaceSheet}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center"
            title={currentWorkspace?.name || 'Workspace'}
            aria-label="Workspaces"
            aria-expanded={workspaceOpen}
          >
            <WorkspaceMarkFrame
              backgroundColor={
                currentWorkspace?.theme?.logoUrl
                  ? undefined
                  : (currentWorkspace?.theme?.primaryColor || '#22c55e')
              }
              className="h-9 w-9"
            >
              <WorkspaceMark
                name={currentWorkspace?.name}
                icon={currentWorkspace?.icon}
                logoUrl={currentWorkspace?.theme?.logoUrl}
                logoEmoji={currentWorkspace?.theme?.logoEmoji}
                fallbackLetter="Z"
                letterClassName="text-sm font-bold text-white"
              />
            </WorkspaceMarkFrame>
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
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center overflow-hidden rounded-full"
            aria-label="Account menu"
            aria-haspopup="menu"
            aria-expanded={profileOpen}
          >
            <UserAvatar user={user} className="h-8 w-8" alt="" />
          </button>
        )}
      </header>

      {workspaceOpen && mounted && createPortal(
        <div
          className="fixed inset-0 z-[300]"
          role="dialog"
          aria-modal="true"
          aria-label="Workspaces"
          data-org-branded="true"
        >
          <button
            type="button"
            className="absolute inset-0 bg-black/40"
            aria-label="Close"
            onClick={() => setWorkspaceOpen(false)}
          />
          <div
            className={cn(
              'absolute inset-x-0 bottom-0 flex max-h-[85vh] flex-col border border-border/60 bg-background shadow-xl',
              'animate-in slide-in-from-bottom duration-200',
            )}
            style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
          >
            <div className="flex items-center justify-between px-4 pt-3 pb-2">
              <span className="text-sm font-semibold">Workspaces</span>
              <button
                type="button"
                onClick={() => setWorkspaceOpen(false)}
                className="p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Close workspaces"
              >
                <X size={18} />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-2">
              <WorkspacesSection onPicked={() => setWorkspaceOpen(false)} />
            </div>
          </div>
        </div>,
        document.body
      )}

      {profileOpen && mounted && createPortal(
        <div>
          <div className="fixed inset-0 z-[299]" onClick={() => setProfileOpen(false)} />
          <AccountMenuPanel
            user={user}
            onClose={() => setProfileOpen(false)}
            className="fixed"
            style={{ top: profilePos.top, right: profilePos.right }}
          />
        </div>,
        document.body
      )}
    </>
  );
}
