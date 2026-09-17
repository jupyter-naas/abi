'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams, useRouter, useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  appsLastOpenKey, appsPath, forgetAppsLastOpen, nextAppsRestoreUrl, shouldSkipAppsRestore,
} from './lib/apps-route';
import {
  AppWindow, ExternalLink, RefreshCw, AlertTriangle, Info,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { isBundledAppHtmlUrl, resolveAppEmbedUrl, resolveAppExternalUrl, appHtmlPathPrefix, pagesSsoAudience, withAppHtmlAccessToken, withPagesSsoToken } from '@/lib/app-html';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useTenant } from '@/contexts/tenant-context';
import { useWorkspaceStore } from '@/stores/workspace';
import { usePublishFeatureResource } from '@/stores/feature-pane';
import { usePrompt } from '@/components/ui/dialogs';
import { appEditorPath, appProjectsApi, type AppProject } from '@/lib/app-projects';
import { AppsMenuBar, type AppsMenuEntry } from '@/components/apps-builder/apps-menu-bar';
import { ViewBar } from './components/view-bar';
import { DatabaseBody } from './components/views';
import { useAppViews } from './components/use-app-views';
import {
  applyFilters, applySearch, applySort, groupRecords, recordToOpenModule, toRecord, toTenantRecord,
  type AppRecord, type AppsResponse,
} from './components/types';

// Editing an app (duplicate a module app into an app project, then open the
// Apps editor) is off while the project workflow is being reworked. The menu
// still shows, greyed: the bar keeps its shape and the feature stays visible
// as something that is coming back. Flip this on to make it live again.
const APP_EDIT_ENABLED = false;

// ---------------------------------------------------------------------------
// Embed view
// ---------------------------------------------------------------------------

function EmbedView({
  record,
  records,
  projects,
  onBack,
  onNewApp,
  onEdit,
  onOpenProject,
}: {
  record: AppRecord;
  /** Every app in the workspace: the Edit menu picks its target from here. */
  records: AppRecord[];
  projects: AppProject[];
  onBack: () => void;
  onNewApp: () => void;
  /** Module apps only: duplicate into an app project and open the editor. */
  onEdit?: (target: AppRecord) => void;
  onOpenProject: (project: AppProject) => void;
}) {
  const url = record.url;
  const baseEmbedUrl = useMemo(() => resolveAppEmbedUrl(url), [url]);
  const [embedUrl, setEmbedUrl] = useState<string | null>(
    isBundledAppHtmlUrl(url) ? null : baseEmbedUrl,
  );
  const [embedError, setEmbedError] = useState<string | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { activePanelSection, setActivePanelSection, appDetailOpen, setAppDetailOpen } =
    useWorkspaceStore();

  useEffect(() => {
    let cancelled = false;
    setEmbedError(null);

    if (!isBundledAppHtmlUrl(url)) {
      const audience = pagesSsoAudience(baseEmbedUrl);
      if (!audience) {
        setEmbedUrl(baseEmbedUrl);
        return () => {
          cancelled = true;
        };
      }
      setEmbedUrl(null);
      (async () => {
        try {
          const res = await authFetch('/api/apps/sso-token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ audience }),
          });
          if (!res.ok) {
            if (!cancelled) setEmbedUrl(baseEmbedUrl);
            return;
          }
          const data = (await res.json()) as { token?: string };
          const token = String(data.token || '').trim();
          if (!cancelled) {
            setEmbedUrl(token ? withPagesSsoToken(baseEmbedUrl, token) : baseEmbedUrl);
          }
        } catch {
          if (!cancelled) setEmbedUrl(baseEmbedUrl);
        }
      })();
      return () => {
        cancelled = true;
      };
    }

    setEmbedUrl(null);
    const prefix = appHtmlPathPrefix(url);
    (async () => {
      try {
        const res = await authFetch('/api/apps/access-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            expires_minutes: 60,
            path_prefix: prefix,
          }),
        });
        if (!res.ok) {
          throw new Error(`access-token HTTP ${res.status}`);
        }
        const data = (await res.json()) as { access_token?: string };
        const token = String(data.access_token || '').trim();
        if (!token) {
          throw new Error('access-token response missing token');
        }
        if (!cancelled) {
          setEmbedUrl(withAppHtmlAccessToken(baseEmbedUrl, token));
        }
      } catch (err) {
        if (!cancelled) {
          setEmbedError(err instanceof Error ? err.message : 'Failed to mint app token');
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [url, baseEmbedUrl, reloadKey]);

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

  const externalHref = embedUrl || resolveAppExternalUrl(url);

  const headerBtn = (active: boolean) =>
    cn(
      'flex h-8 w-8 items-center justify-center rounded-md transition-all',
      'hover:bg-muted hover:text-foreground',
      active ? 'bg-muted text-foreground' : 'text-muted-foreground',
    );

  // Edit names its target instead of assuming the open app: the list is every
  // app in the workspace, current one ticked, plus the app projects that open
  // straight in the editor. Apps that cannot be edited stay visible but greyed,
  // so the menu reads as the whole catalogue rather than a filtered remnant.
  const editItems: AppsMenuEntry[] = [
    { id: 'apps-heading', label: 'Apps', heading: true },
    ...records.map((candidate) => ({
      id: `app-${candidate.id}`,
      label: candidate.name,
      checked: candidate.id === record.id,
      disabled: candidate.source !== 'module' || !onEdit,
      title:
        candidate.source === 'module'
          ? `Edit a copy of ${candidate.name} in the Apps editor`
          : `${candidate.name} is an external app — there is no source to edit`,
      onSelect: () => onEdit?.(candidate),
    })),
    ...(projects.length
      ? [
          { id: 'sep-projects', separator: true },
          { id: 'projects-heading', label: 'App projects', heading: true },
          ...projects.map((project) => ({
            id: `project-${project.slug}`,
            label: `${project.icon_emoji ? `${project.icon_emoji} ` : ''}${project.title}`,
            title: `Open ${project.title} in the Apps editor`,
            onSelect: () => onOpenProject(project),
          })),
        ]
      : []),
  ];

  return (
    <div className="flex h-full flex-col">
      <Header
        title={record.name}
        nav={
          <AppsMenuBar
            onNewApp={onNewApp}
            fileExtras={[{ id: 'all-apps', label: 'All apps', onSelect: onBack }]}
            editItems={editItems}
            editDisabled={!APP_EDIT_ENABLED}
            editDisabledTitle="Editing an app is temporarily unavailable"
            trailing={
              <span className="ml-2 min-w-0 truncate border-l border-border pl-2 text-xs font-medium text-foreground">
                {record.name}
              </span>
            }
          />
        }
        actions={
          <>
            <button
              type="button"
              onClick={toggleDetail}
              title={detailShown ? 'Hide details' : 'Show details'}
              className={headerBtn(detailShown)}
            >
              <Info size={16} />
            </button>
            <button
              type="button"
              onClick={handleReload}
              title="Reload"
              className={headerBtn(false)}
            >
              <RefreshCw size={16} />
            </button>
            <a
              href={externalHref}
              target="_blank"
              rel="noopener noreferrer"
              title="Open in new tab"
              className={headerBtn(false)}
            >
              <ExternalLink size={16} />
            </a>
          </>
        }
      />

      {/* Body: full-width iframe. Detail lives in the left section panel. */}
      <div className="relative flex-1 overflow-hidden bg-muted/20">
        {embedError ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
            <AlertTriangle size={36} className="text-amber-500" />
            <div>
              <p className="font-semibold text-foreground">Could not open app</p>
              <p className="mt-1 max-w-xs text-sm text-muted-foreground">{embedError}</p>
            </div>
            <button
              type="button"
              onClick={handleReload}
              className="flex items-center gap-2 bg-workspace-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-workspace-accent/90"
            >
              <RefreshCw size={14} />
              Retry
            </button>
          </div>
        ) : blocked ? (
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
              href={externalHref}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-workspace-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-workspace-accent/90"
            >
              <ExternalLink size={14} />
              Open {record.name}
            </a>
          </div>
        ) : !embedUrl ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Preparing secure app session…
          </div>
        ) : (
          <iframe
            key={`${reloadKey}:${embedUrl}`}
            ref={iframeRef}
            src={embedUrl}
            title={record.name}
            onLoad={handleLoad}
            className="h-full w-full border-0"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-presentation allow-downloads"
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
// App projects (built or copied in Nexus)
// ---------------------------------------------------------------------------

function AppProjectsStrip({ projects, onOpen }: { projects: AppProject[]; onOpen: (p: AppProject) => void }) {
  if (!projects.length) return null;
  return (
    <section className="mb-6">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        App projects
      </h2>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(14rem,1fr))] gap-2">
        {projects.map((project) => (
          <button
            key={project.slug}
            type="button"
            onClick={() => onOpen(project)}
            className="flex items-start gap-2 border border-border bg-background p-3 text-left transition-colors hover:border-workspace-accent/50 hover:bg-muted/40"
          >
            <span className="text-lg leading-none">{project.icon_emoji || '✨'}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-foreground">{project.title}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {project.submission
                  ? `Submitted · ${project.submission.branch}`
                  : project.origin
                    ? `Copy of ${project.origin.app_id}`
                    : 'Built in Nexus'}
              </span>
            </span>
            {project.dirty && (
              <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-500" title="Unsaved changes" />
            )}
          </button>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AppsPage() {
  const tenant = useTenant();
  const params = useParams();
  const urlWorkspaceId = params.workspaceId as string;
  const { currentWorkspaceId, setOpenAppModule, setAppDetailOpen } = useWorkspaceStore();
  const searchParams = useSearchParams();
  const router = useRouter();

  const [apps, setApps] = useState<AppRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeApp, setActiveApp] = useState<AppRecord | null>(null);
  const [search, setSearch] = useState('');
  const [projects, setProjects] = useState<AppProject[]>([]);
  const [projectError, setProjectError] = useState<string | null>(null);
  const { prompt, dialog: promptDialog } = usePrompt();

  const views = useAppViews(urlWorkspaceId);

  // App projects need git storage; without it the section stays hidden.
  useEffect(() => {
    if (!urlWorkspaceId) return;
    appProjectsApi.list(urlWorkspaceId).then(setProjects).catch(() => setProjects([]));
  }, [urlWorkspaceId]);

  const handleNewApp = async () => {
    const title = await prompt({
      title: 'New app',
      description: 'A static app (HTML, CSS, JavaScript) you build with the Apps agent.',
      placeholder: 'Your App Name',
      confirmLabel: 'Create',
    });
    if (!title) return;
    try {
      const created = await appProjectsApi.create(urlWorkspaceId, title.trim());
      router.push(appEditorPath(urlWorkspaceId, created.slug));
    } catch (e) {
      setProjectError((e as Error).message);
    }
  };

  const handleEditModuleApp = async (record: AppRecord) => {
    try {
      const copy = await appProjectsApi.importModuleApp(urlWorkspaceId, record.id);
      router.push(appEditorPath(urlWorkspaceId, copy.slug));
    } catch (e) {
      setProjectError((e as Error).message);
    }
  };

  // The open app rides into the right chat pane: manifest ``agent`` overrides
  // the Apps office agent when the workspace lists that agent.
  usePublishFeatureResource(
    activeApp
      ? {
          feature: 'apps',
          kind: 'app',
          id: activeApp.id,
          label: activeApp.name,
          ...(activeApp.app?.agent ? { agent: activeApp.app.agent } : {}),
        }
      : null,
  );

  useEffect(() => {
    return () => {
      setOpenAppModule(null);
      setAppDetailOpen(false);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Restore last opened app when landing on the section without ?open=.
  // Keyed on the URL workspace, not the store: the store lags a workspace
  // switch and used to rewrite Valeo back to the previous workspace.
  useEffect(() => {
    const key = appsLastOpenKey(urlWorkspaceId);
    if (!urlWorkspaceId || !key) return;
    try {
      const saved = sessionStorage.getItem(key);
      const next = nextAppsRestoreUrl({
        urlWorkspaceId,
        storeWorkspaceId: currentWorkspaceId,
        searchOpen: searchParams?.get('open'),
        savedOpen: saved,
        skipRestore: shouldSkipAppsRestore(),
      });
      if (next) router.replace(next);
    } catch {
      // sessionStorage unavailable (e.g. private mode restrictions) — ignore
    }
  }, [urlWorkspaceId, currentWorkspaceId, searchParams, router]);

  useEffect(() => {
    const apiBase = getApiUrl();
    if (!urlWorkspaceId) return;
    setLoading(true);
    authFetch(`${apiBase}/api/apps/?workspace_id=${encodeURIComponent(urlWorkspaceId)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((data: AppsResponse) => {
        setApps(
          data.apps.filter((a) => a.installed && a.url && a.enabled).map(toRecord),
        );
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [urlWorkspaceId]);

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

  const lastOpenKey = appsLastOpenKey(urlWorkspaceId);

  const handleClose = () => {
    setActiveApp(null);
    setOpenAppModule(null);
    setAppDetailOpen(false);
    forgetAppsLastOpen(urlWorkspaceId);
    router.replace(appsPath(urlWorkspaceId));
  };

  // Opening an app never forces the metadata panel open — that stays opt-in.
  const handleOpen = (record: AppRecord) => {
    setActiveApp(record);
    setOpenAppModule(record.source === 'module' ? recordToOpenModule(record) : null);
    if (lastOpenKey) sessionStorage.setItem(lastOpenKey, record.id);
    router.replace(appsPath(urlWorkspaceId, record.id));
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
        {projectError && (
          <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
            {projectError}
          </div>
        )}
        <EmbedView
          record={activeApp}
          records={records}
          projects={projects}
          onBack={handleClose}
          onNewApp={() => void handleNewApp()}
          onEdit={(target) => void handleEditModuleApp(target)}
          onOpenProject={(project) => router.push(appEditorPath(urlWorkspaceId, project.slug))}
        />
      </div>
    );
  }

  const isEmpty = !loading && !error && visibleCount === 0;

  return (
    <div className="flex h-full flex-col">
      <Header
        title="Apps"
        subtitle="Your installed and configured apps"
        nav={<AppsMenuBar onNewApp={() => void handleNewApp()} />}
      />
      {promptDialog}
      {projectError && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {projectError}
        </div>
      )}

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
          <AppProjectsStrip
            projects={projects}
            onOpen={(project) => router.push(appEditorPath(urlWorkspaceId, project.slug))}
          />
          {isEmpty && <EmptyState filtered={records.length > 0} />}
          {!loading && !error && visibleCount > 0 && (
            <DatabaseBody view={view} groups={groups} onOpen={handleOpen} />
          )}
        </div>
      </div>
    </div>
  );
}
