'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  AppWindow, ExternalLink, RefreshCw, AlertTriangle, Info, PanelLeft, X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { isBundledAppHtmlUrl, resolveAppEmbedUrl, resolveAppExternalUrl } from '@/lib/app-html';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useTenant } from '@/contexts/tenant-context';
import { useWorkspaceStore } from '@/stores/workspace';
import { ViewBar } from './components/view-bar';
import { DatabaseBody } from './components/views';
import { useAppViews } from './components/use-app-views';
import {
  applyFilters, applySearch, applySort, groupRecords, recordToOpenModule, toRecord, toTenantRecord,
  type AppRecord, type AppsResponse,
} from './components/types';

// ---------------------------------------------------------------------------
// Embed view
// ---------------------------------------------------------------------------

function EmbedView({ record, onBack }: { record: AppRecord; onBack: () => void }) {
  const url = record.url;
  const embedUrl = useMemo(() => resolveAppEmbedUrl(url), [url]);
  const [blocked, setBlocked] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { activePanelSection, setActivePanelSection, appDetailOpen, setAppDetailOpen } =
    useWorkspaceStore();

  const handleLoad = useCallback(() => {
    // Same-origin bundled apps are proxied via /app-html/ — never flag them blocked.
    if (isBundledAppHtmlUrl(url)) {
      setBlocked(false);
      return;
    }
    try {
      const doc = iframeRef.current?.contentDocument;
      if (doc && (!doc.body || doc.body.innerHTML === '')) {
        setBlocked(true);
        return;
      }
    } catch {
      // SecurityError = cross-origin page loaded successfully.
    }
    setBlocked(false);
  }, [url]);

  const handleReload = () => {
    setBlocked(false);
    setReloadKey((k) => k + 1);
  };

  // Metadata is opt-in: the panel only shows it when the user asks for it here.
  const detailShown = activePanelSection === 'apps' && appDetailOpen;
  const toggleDetail = () => {
    if (detailShown) {
      setAppDetailOpen(false);
      return;
    }
    setAppDetailOpen(true);
    setActivePanelSection('apps');
  };

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex h-12 flex-shrink-0 items-center gap-2 border-b border-border/50 bg-background px-3">
        <button
          onClick={() => setActivePanelSection(activePanelSection === 'apps' ? null : 'apps')}
          title={activePanelSection === 'apps' ? 'Close panel' : 'Open panel'}
          className={cn(
            'flex h-7 w-7 flex-shrink-0 items-center justify-center rounded transition-colors',
            activePanelSection === 'apps'
              ? 'bg-muted text-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          )}
        >
          <PanelLeft size={15} />
        </button>
        <span className="flex-1 truncate text-sm font-medium">{record.name}</span>
        <button
          onClick={toggleDetail}
          title={detailShown ? 'Hide details' : 'Show details'}
          className={cn(
            'rounded p-1.5 transition-colors',
            detailShown
              ? 'bg-muted text-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          )}
        >
          <Info size={13} />
        </button>
        <button
          onClick={handleReload}
          title="Reload"
          className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <RefreshCw size={13} />
        </button>
        <a
          href={resolveAppExternalUrl(url)}
          target="_blank"
          rel="noopener noreferrer"
          title="Open in new tab"
          className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <ExternalLink size={13} />
        </a>
        <button
          onClick={onBack}
          title="Close app"
          className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <X size={14} />
        </button>
      </div>

      {/* Body: full-width iframe — detail lives in the left section panel */}
      <div className="relative flex-1 overflow-hidden bg-muted/20">
        {blocked ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
            <AlertTriangle size={36} className="text-amber-500" />
            <div>
              <p className="font-semibold text-foreground">Embedding blocked</p>
              <p className="mt-1 max-w-xs text-sm text-muted-foreground">
                This site has disabled embedding via{' '}
                <code className="rounded bg-muted px-1 py-0.5 text-xs">X-Frame-Options</code>. Open it
                in a new tab instead.
              </p>
            </div>
            <a
              href={resolveAppExternalUrl(url)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-workspace-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-workspace-accent/90"
            >
              <ExternalLink size={14} />
              Open {record.name}
            </a>
          </div>
        ) : (
          <iframe
            key={reloadKey}
            ref={iframeRef}
            src={embedUrl}
            title={record.name}
            onLoad={handleLoad}
            className="h-full w-full border-0"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-presentation"
            allow="fullscreen"
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState({ filtered }: { filtered: boolean }) {
  if (filtered) {
    return (
      <p className="py-16 text-center text-sm text-muted-foreground">
        No apps match this view. Adjust the search or the filters.
      </p>
    );
  }
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
      <AppWindow size={40} className="text-muted-foreground/30" />
      <div>
        <p className="font-medium text-foreground">No apps installed yet</p>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          Install modules from the Marketplace to see their apps here.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AppsPage() {
  const tenant = useTenant();
  const { currentWorkspaceId, setOpenAppModule, setAppDetailOpen } = useWorkspaceStore();
  const searchParams = useSearchParams();
  const router = useRouter();

  const [apps, setApps] = useState<AppRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeApp, setActiveApp] = useState<AppRecord | null>(null);
  const [search, setSearch] = useState('');

  const views = useAppViews(currentWorkspaceId);

  useEffect(() => {
    return () => {
      setOpenAppModule(null);
      setAppDetailOpen(false);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Restore last opened app when navigating back to the section without ?open=
  useEffect(() => {
    if (!currentWorkspaceId) return;
    if (searchParams?.get('open')) return;
    try {
      const saved = sessionStorage.getItem(`nexus.apps.last_open.${currentWorkspaceId}`);
      if (saved) {
        router.replace(`/workspace/${currentWorkspaceId}/apps?open=${encodeURIComponent(saved)}`);
      }
    } catch {
      // sessionStorage unavailable (e.g. private mode restrictions) — ignore
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentWorkspaceId]);

  useEffect(() => {
    const apiBase = getApiUrl();
    if (!currentWorkspaceId) return;
    setLoading(true);
    authFetch(`${apiBase}/api/apps/?workspace_id=${encodeURIComponent(currentWorkspaceId)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((data: AppsResponse) => {
        setApps(
          data.apps.filter((a) => a.installed && a.url && a.enabled).map(toRecord),
        );
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentWorkspaceId]);

  // Module apps and tenant-level external apps are one database. "Source" is a
  // property you can filter or group by — not a separate section.
  const records = useMemo(
    () => [...apps, ...tenant.apps.map(toTenantRecord)],
    [apps, tenant.apps],
  );

  // Sync activeApp with ?open= so navigating back to the database (without the
  // query param) clears the embed view.
  useEffect(() => {
    const openParam = searchParams?.get('open');
    if (!openParam) {
      setActiveApp(null);
      setOpenAppModule(null);
      setAppDetailOpen(false);
      return;
    }
    const record =
      records.find((r) => r.id === openParam) ??
      records.find((r) => r.modulePath === openParam);
    if (!record) return;
    setActiveApp(record);
    setOpenAppModule(record.source === 'module' ? recordToOpenModule(record) : null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, records]);

  const lastOpenKey = currentWorkspaceId ? `nexus.apps.last_open.${currentWorkspaceId}` : null;

  const handleClose = () => {
    setActiveApp(null);
    setOpenAppModule(null);
    setAppDetailOpen(false);
    if (lastOpenKey) sessionStorage.removeItem(lastOpenKey);
    router.replace(`/workspace/${currentWorkspaceId}/apps`);
  };

  // Opening an app never forces the metadata panel open — that stays opt-in.
  const handleOpen = (record: AppRecord) => {
    setActiveApp(record);
    setOpenAppModule(record.source === 'module' ? recordToOpenModule(record) : null);
    if (lastOpenKey) sessionStorage.setItem(lastOpenKey, record.id);
    router.replace(
      `/workspace/${currentWorkspaceId}/apps?open=${encodeURIComponent(record.id)}`,
    );
  };

  const view = views.activeView;
  const groups = useMemo(() => {
    const filtered = applySort(
      applySearch(applyFilters(records, view.filters), search),
      view.sort,
    );
    // A board always needs an axis; fall back to module when none is set.
    const groupBy = view.type === 'board' ? view.groupBy ?? 'module' : view.groupBy;
    return groupRecords(filtered, groupBy);
  }, [records, view, search]);

  const visibleCount = useMemo(
    () => new Set(groups.flatMap((g) => g.records.map((r) => r.id))).size,
    [groups],
  );

  // Embed view: replaces the entire page body
  if (activeApp) {
    return (
      <div className="flex h-full flex-col">
        <EmbedView record={activeApp} onBack={handleClose} />
      </div>
    );
  }

  const isEmpty = !loading && !error && visibleCount === 0;

  return (
    <div className="flex h-full flex-col">
      <Header title="Apps" subtitle="Your installed and configured apps" />

      <ViewBar
        api={views}
        records={records}
        search={search}
        onSearchChange={setSearch}
        count={visibleCount}
      />

      <div className="flex-1 overflow-auto">
        <div className="p-6">
          {loading && (
            <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
              <AppWindow size={18} className="mr-2 animate-pulse" /> Loading apps...
            </div>
          )}
          {error && (
            <div className="border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
              Failed to load: {error}
            </div>
          )}
          {isEmpty && <EmptyState filtered={records.length > 0} />}
          {!loading && !error && visibleCount > 0 && (
            <DatabaseBody view={view} groups={groups} onOpen={handleOpen} />
          )}
        </div>
      </div>
    </div>
  );
}
