'use client';

import { useMemo, type ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { ExternalLink, GitBranch, RefreshCw } from 'lucide-react';
import { ApiStatusIndicator } from '@/components/shell/api-status-indicator';
import { useAuthStore } from '@/stores/auth';
import { useCodeStore } from '@/stores/code';
import { useFilesStore } from '@/stores/files';
import { usePlatformStatusStore } from '@/stores/platform-status';
import { useSlidesStore } from '@/stores/slides';
import { useWorkspaceStore } from '@/stores/workspace';
import { cn } from '@/lib/utils';

/** Empty field glyph when a slot does not apply to the current surface. */
const NA = '\u2014';

/** Default Forgejo repo for Slides decks (matches API `coding_repo_id` default). */
const SLIDES_DEFAULT_REPO = 'abi/monorepo';

function statusLabel(status: string, phase: string | null): string {
  if (status === 'ready') return phase || 'ready';
  if (status === 'degraded') return phase || 'degraded';
  if (status === 'error') return phase || 'unavailable';
  if (status === 'ensuring') return 'starting';
  if (status === 'running') return phase || 'running';
  if (phase) return phase;
  return status || 'idle';
}

function statusDotClass(status: string): string {
  if (status === 'ready' || status === 'running') return 'bg-green-500';
  if (status === 'degraded' || status === 'ensuring' || status === 'starting') {
    return 'bg-amber-500 animate-pulse';
  }
  if (status === 'error' || status === 'failed') return 'bg-red-500';
  return 'bg-muted-foreground/40';
}

function parseCodeRepoFromPath(pathname: string): string | null {
  const match = pathname.match(/\/code\/r\/([^/]+)\/([^/]+)/);
  if (!match) return null;
  return `${decodeURIComponent(match[1])}/${decodeURIComponent(match[2])}`;
}

function Slot({
  label,
  value,
  title,
  mono,
  leading,
}: {
  label: string;
  value: string;
  title?: string;
  mono?: boolean;
  leading?: ReactNode;
}) {
  const empty = value === NA;
  return (
    <span
      className="inline-flex min-w-0 max-w-[14rem] items-center gap-1.5"
      title={title ?? `${label}: ${value}`}
    >
      {leading}
      <span className="shrink-0 text-muted-foreground/70">{label}</span>
      <span
        className={cn(
          'truncate',
          mono && 'font-mono',
          empty ? 'text-muted-foreground/60' : 'font-medium text-foreground/90',
        )}
      >
        {value}
      </span>
    </span>
  );
}

/**
 * Thin platform status footer for every Nexus workspace section.
 * Left: User / Business workspace / Repo / Branch / Code workspace [/ dirty]
 * Right: Refresh + API health
 *
 * Terminology: see Zen docs/ux/business-vs-code-workspace.md
 */
export function PlatformStatusFooter() {
  const pathname = usePathname() || '';
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const fetchWorkspaces = useWorkspaceStore((s) => s.fetchWorkspaces);

  const onRefresh = usePlatformStatusStore((s) => s.onRefresh);
  const refreshTitle = usePlatformStatusStore((s) => s.refreshTitle);
  const refreshing = usePlatformStatusStore((s) => s.refreshing);
  const repoOverride = usePlatformStatusStore((s) => s.repoOverride);
  const branchOverride = usePlatformStatusStore((s) => s.branchOverride);
  const coderWorkspaceOverride = usePlatformStatusStore((s) => s.coderWorkspaceOverride);
  const coderPhaseOverride = usePlatformStatusStore((s) => s.coderPhaseOverride);
  const coderStatusOverride = usePlatformStatusStore((s) => s.coderStatusOverride);
  const coderUiUrlOverride = usePlatformStatusStore((s) => s.coderUiUrlOverride);
  const dirtyOverride = usePlatformStatusStore((s) => s.dirtyOverride);

  const selectedRepoId = useCodeStore((s) => s.selectedRepoId);
  const codeBranch = useCodeStore((s) => s.activeBranch);
  const codeCoder = useCodeStore((s) => s.coderWorkspace);
  const codePhase = useCodeStore((s) => s.coderPhase);
  const codeCoderUiUrl = useCodeStore((s) => s.coderUiUrl);
  const unsavedChanges = useFilesStore((s) => s.unsavedChanges);

  const slidesRuntimeStatus = useSlidesStore((s) => s.runtimeStatus);
  const forgejoBranch = useSlidesStore((s) => s.forgejoBranch);
  const coderWorkspace = useSlidesStore((s) => s.coderWorkspace);
  const coderPhase = useSlidesStore((s) => s.coderPhase);
  const slidesCoderUiUrl = useSlidesStore((s) => s.coderUiUrl);
  const selectedSlug = useSlidesStore((s) => s.selectedSlug);
  const deckDirty = useSlidesStore((s) => s.deckDirty);
  const deckSource = useSlidesStore((s) => s.deckSource);
  const requestDeckRefresh = useSlidesStore((s) => s.requestDeckRefresh);

  const isSlides = pathname.includes('/slides');
  const isCode = pathname.includes('/code') || pathname.includes('/ide');
  const pathRepo = parseCodeRepoFromPath(pathname);

  const currentWorkspace = useMemo(
    () => workspaces.find((w) => w.id === currentWorkspaceId),
    [workspaces, currentWorkspaceId],
  );

  const userLabel = user?.name?.trim() || user?.email?.trim() || null;

  // Product "Workspace" in Nexus = Business Workspace name (not Coder).
  const businessWorkspaceLabel = currentWorkspace?.name?.trim() || null;

  const slidesBranch =
    forgejoBranch || (selectedSlug ? `slides/${selectedSlug}` : null);
  const slidesCoder =
    coderWorkspace || (selectedSlug ? `slides-${selectedSlug}` : null);

  const repo = (() => {
    if (repoOverride) return repoOverride;
    if (isSlides && (slidesBranch || selectedSlug)) return SLIDES_DEFAULT_REPO;
    if (isCode) return pathRepo || selectedRepoId || null;
    return null;
  })();

  const branch = (() => {
    if (branchOverride) return branchOverride;
    if (isSlides) return slidesBranch;
    if (isCode) return codeBranch;
    return null;
  })();

  const coderName = (() => {
    if (coderWorkspaceOverride) return coderWorkspaceOverride;
    if (isSlides) return slidesCoder;
    if (isCode) return codeCoder;
    return null;
  })();

  const coderStatus = (() => {
    if (coderStatusOverride) return coderStatusOverride;
    if (isSlides) return slidesRuntimeStatus;
    if (isCode && codePhase) return codePhase;
    return null;
  })();

  const coderPhaseLabel = (() => {
    if (coderPhaseOverride) return coderPhaseOverride;
    if (isSlides) return coderPhase;
    if (isCode) return codePhase;
    return null;
  })();

  const coderUiUrl = (() => {
    if (coderUiUrlOverride) return coderUiUrlOverride;
    if (isSlides) return slidesCoderUiUrl;
    if (isCode) return codeCoderUiUrl;
    return null;
  })();

  const dirtyState = (() => {
    if (dirtyOverride !== null && dirtyOverride !== undefined) {
      return dirtyOverride;
    }
    if (isSlides && selectedSlug) return deckDirty;
    if (isCode) {
      return Object.values(unsavedChanges || {}).some(Boolean);
    }
    return null;
  })();

  const handleRefresh = () => {
    if (onRefresh) {
      onRefresh();
      return;
    }
    if (isSlides) {
      requestDeckRefresh(selectedSlug);
      return;
    }
    void fetchWorkspaces();
    router.refresh();
  };

  const codeWorkspaceValue = coderName
    ? `${coderName} ${statusLabel(coderStatus || 'idle', coderPhaseLabel)}`
    : NA;

  const dirtyTitle = (() => {
    if (dirtyState === null) return undefined;
    if (dirtyState) {
      if (isSlides) {
        return 'Local buffer differs from last Save';
      }
      return 'Open files have unsaved changes';
    }
    if (isSlides && deckSource === 'forgejo') {
      return 'Saved locally; preview is a Forgejo snapshot (sidecar not ready)';
    }
    if (isSlides && deckSource === 'sidecar') {
      return 'Saved; preview matches Coder workspace';
    }
    return 'No unsaved local changes';
  })();

  return (
    <footer
      className={cn(
        'flex h-7 shrink-0 items-center justify-between gap-3 border-t border-border/60',
        'bg-muted/40 px-3 text-[11px] text-muted-foreground',
      )}
      data-platform-status-footer="true"
    >
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden sm:gap-3">
        <Slot label="User" value={userLabel || NA} title={user?.email || undefined} />
        <span className="text-border/80" aria-hidden>
          /
        </span>
        <Slot
          label="Business workspace"
          value={businessWorkspaceLabel || NA}
          title={
            currentWorkspace
              ? `Business workspace: ${currentWorkspace.name} (${currentWorkspace.id})`
              : 'Business workspace (Nexus collaboration space)'
          }
        />
        <span className="text-border/80" aria-hidden>
          /
        </span>
        <Slot label="Repo" value={repo || NA} mono title="Forgejo / git repository" />
        <span className="text-border/80" aria-hidden>
          /
        </span>
        <Slot
          label="Branch"
          value={branch || NA}
          mono
          title="Git branch for current coding or slides context"
          leading={
            branch ? <GitBranch size={11} className="shrink-0 opacity-70" /> : undefined
          }
        />
        <span className="text-border/80" aria-hidden>
          /
        </span>
        <span
          className="inline-flex min-w-0 max-w-[18rem] items-center gap-1.5"
          title={
            coderUiUrl
              ? `Open Code workspace in Coder: ${coderUiUrl}`
              : 'Code workspace (Coder runtime / engineering environment)'
          }
        >
          {coderName ? (
            <span
              className={cn(
                'inline-block h-1.5 w-1.5 shrink-0 rounded-sm',
                statusDotClass(coderStatus || 'idle'),
              )}
              aria-hidden
            />
          ) : null}
          <span className="shrink-0 text-muted-foreground/70">Code workspace</span>
          {coderName && coderUiUrl ? (
            <a
              href={coderUiUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                'inline-flex min-w-0 max-w-[14rem] items-center gap-1 truncate',
                'font-mono font-medium text-foreground/90 underline-offset-2',
                'hover:text-foreground hover:underline',
              )}
              title={`Open in Coder: ${coderUiUrl}`}
            >
              <span className="truncate">{codeWorkspaceValue}</span>
              <ExternalLink size={10} className="shrink-0 opacity-70" aria-hidden />
            </a>
          ) : (
            <span
              className={cn(
                'truncate font-mono',
                coderName ? 'font-medium text-foreground/90' : 'text-muted-foreground/60',
              )}
            >
              {codeWorkspaceValue}
            </span>
          )}
        </span>
        {dirtyState !== null ? (
          <>
            <span className="text-border/80" aria-hidden>
              /
            </span>
            <span
              className={cn(
                'inline-flex shrink-0 items-center gap-1',
                dirtyState ? 'font-medium text-amber-600' : 'text-muted-foreground/80',
              )}
              title={dirtyTitle}
              data-dirty={dirtyState ? 'true' : 'false'}
            >
              {dirtyState ? (
                <>
                  <span aria-hidden>●</span>
                  <span>Unsaved changes</span>
                </>
              ) : (
                <span>Saved</span>
              )}
            </span>
          </>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-0.5">
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className={cn(
            'inline-flex items-center gap-1 rounded px-1.5 py-0.5 transition-colors',
            'hover:bg-muted hover:text-foreground',
            refreshing && 'opacity-60',
          )}
          title={refreshTitle}
        >
          <RefreshCw size={11} className={cn(refreshing && 'animate-spin')} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
        <ApiStatusIndicator compact />
      </div>
    </footer>
  );
}
