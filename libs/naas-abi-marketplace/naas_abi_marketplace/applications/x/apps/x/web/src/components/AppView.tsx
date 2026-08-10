"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useAppState } from "@/components/AppProvider";
import { Shell } from "@/components/Shell";
import { Filters } from "@/components/Filters";
import { CountPage } from "@/components/pages/CountPage";
import { ParametersPage } from "@/components/pages/ParametersPage";
import { SearchPage } from "@/components/pages/SearchPage";
import { UsersPage } from "@/components/pages/UsersPage";
import {
  hasParams,
  hrefFor,
  NO_PARAMS,
  readParams,
  subscribeToParams,
  writeParams,
} from "@/lib/routes";
import type { PageParams } from "@/lib/routes";
import type { PageKey } from "@/lib/types";

type Props = {
  /** Which page this route renders. Every page mounts the same view. */
  page: PageKey;
};

/** The requested id when the snapshots still publish it, else the first one. */
function resolve<T>(
  items: T[],
  wanted: string,
  idOf: (item: T) => string,
): string {
  if (items.some((item) => idOf(item) === wanted)) return wanted;
  return items[0] ? idOf(items[0]) : "";
}

/**
 * The dashboard, minus the routing.
 *
 * Each route under `app/` renders this with its own ``page``; the query string
 * carries what a path cannot (see `lib/routes.ts`), and everything that must
 * outlive a page change lives in `AppProvider`.
 */
export function AppView({ page }: Props) {
  const {
    data,
    error,
    scenarioId,
    setScenarioId,
    querySlug,
    setQuerySlug,
    timezone,
    setTimezone,
    setPostsPage,
  } = useAppState();
  const [selectedUser, setSelectedUser] = useState<string | null>(null);

  // What the URL this page opened with asked for. The author applies straight
  // away; scenario and query wait for the snapshots to name the published ones.
  const opened = useRef<PageParams>(NO_PARAMS);
  const applied = useRef(false);

  // The URL is read after mount, never during render, so the prerendered HTML
  // still matches what React first paints.
  useEffect(() => {
    const params = readParams();
    opened.current = params;
    setSelectedUser(params.user);
  }, []);

  // Coming back to Posts lands on the subpage last visited.
  useEffect(() => {
    if (page === "count" || page === "search") setPostsPage(page);
  }, [page, setPostsPage]);

  // Filters named by the URL win over the ones already in session; filters it
  // does not mention are left alone, so moving to a page that carries none
  // keeps the selection made on the previous one.
  useEffect(() => {
    if (!data || applied.current) return;
    applied.current = true;
    const params = opened.current;
    const scenario = params.scenario
      ? resolve(data.scenarios, params.scenario, (s) => s.id)
      : "";
    const query = params.query
      ? resolve(data.queries, params.query, (q) => q.slug)
      : "";
    if (scenario) setScenarioId(scenario);
    if (query) setQuerySlug(query);
    // Normalise the opening URL in place — a pasted `?user=@grok`, or a
    // scenario this publish no longer carries, becomes what is on screen, so
    // copying the URL back out shares the view actually being shown. A bare
    // page URL stays bare: nothing was asked for.
    if (hasParams(params)) {
      writeParams(
        page,
        {
          user: params.user,
          scenario: scenario || scenarioId,
          query: query || querySlug,
        },
        "replace",
      );
    }
  }, [data, page, scenarioId, querySlug, setScenarioId, setQuerySlug]);

  // Back / Forward replay whatever the visited URL carried. Params absent from
  // that URL are left alone rather than reset to the first published value.
  useEffect(
    () =>
      subscribeToParams((params) => {
        setSelectedUser(params.user);
        if (!data) return;
        if (params.scenario) {
          setScenarioId(resolve(data.scenarios, params.scenario, (s) => s.id));
        }
        if (params.query) {
          setQuerySlug(resolve(data.queries, params.query, (q) => q.slug));
        }
      }),
    [data, setScenarioId, setQuerySlug],
  );

  // Selecting an author, or clearing the selection, stays on /users/search and
  // is a history entry of its own.
  const handleUserChange = (username: string | null) => {
    setSelectedUser(username);
    writeParams(page, { user: username });
  };

  // Filters refine the page you are already on, so they rewrite the current
  // history entry instead of stacking one per dropdown change.
  const handleScenarioChange = (id: string) => {
    setScenarioId(id);
    writeParams(page, { scenario: id, query: querySlug }, "replace");
  };

  const handleQueryChange = (slug: string) => {
    setQuerySlug(slug);
    writeParams(page, { scenario: scenarioId, query: slug }, "replace");
  };

  // Links out of this page keep the state the target page honours: switching
  // Posts subpages carries the filters over, and leaves the author behind.
  const hrefOf = (target: PageKey) =>
    hrefFor(target, {
      user: selectedUser,
      scenario: scenarioId,
      query: querySlug,
    });

  const builtLabel = useMemo(() => {
    if (!data?.updatedAt) return null;
    try {
      const d = new Date(data.updatedAt);
      return d.toISOString().replace("T", " ").slice(0, 16) + " UTC";
    } catch {
      return data.updatedAt;
    }
  }, [data]);

  if (error) {
    return <div className="status">{error}</div>;
  }

  if (!data) {
    return <div className="status">Loading snapshots…</div>;
  }

  // The Users page searches the whole graph, so scenario / query do not apply.
  const showDataFilters = page === "count" || page === "search";

  return (
    <Shell
      page={page}
      hrefOf={hrefOf}
      builtAt={builtLabel}
      filters={
        showDataFilters ? (
          <Filters
            scenarios={data.scenarios}
            queries={data.queries}
            scenarioId={scenarioId}
            querySlug={querySlug}
            onScenarioChange={handleScenarioChange}
            onQueryChange={handleQueryChange}
          />
        ) : null
      }
    >
      <div className="page-wrap">
        {page === "count" ? (
          <CountPage
            data={data.count}
            querySlug={querySlug}
            scenarioId={scenarioId}
          />
        ) : null}
        {page === "search" ? (
          <SearchPage
            data={data.search}
            querySlug={querySlug}
            scenarioId={scenarioId}
            timezone={timezone}
            scenarios={data.scenarios}
          />
        ) : null}
        {page === "users" ? (
          <UsersPage
            timezone={timezone}
            selected={selectedUser}
            onSelectUser={handleUserChange}
          />
        ) : null}
        {page === "parameters" ? (
          <ParametersPage
            timezones={data.timezones}
            timezone={timezone}
            onTimezoneChange={setTimezone}
          />
        ) : null}
      </div>
    </Shell>
  );
}
