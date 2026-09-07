"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAppState } from "@/components/AppProvider";
import { Shell } from "@/components/Shell";
import { Filters } from "@/components/Filters";
import { CountPage } from "@/components/pages/CountPage";
import { ParametersPage } from "@/components/pages/ParametersPage";
import { PostPage } from "@/components/pages/PostPage";
import { SearchPage } from "@/components/pages/SearchPage";
import { TweetsPage } from "@/components/pages/TweetsPage";
import { UsersPage } from "@/components/pages/UsersPage";
import { pageConfig } from "@/lib/appConfig";
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
    setSectionPage,
  } = useAppState();
  const router = useRouter();
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [selectedPost, setSelectedPost] = useState<string | null>(null);
  const [needle, setNeedle] = useState("");
  /** `?from=` - which page a detail page was opened from. */
  const [origin, setOrigin] = useState<string | null>(null);
  /** `?expand=1` - the post alone, with none of the app's chrome around it. */
  const [expanded, setExpanded] = useState(false);

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
    setSelectedPost(params.post);
    setNeedle(params.q || "");
    setOrigin(params.from);
    setExpanded(params.expand);
  }, []);

  // Coming back to a section lands on the page last visited in it.
  useEffect(() => {
    setSectionPage(page);
    window.scrollTo({ top: 0 });
  }, [page, setSectionPage]);

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
    // Normalise the opening URL in place - a pasted `?user=@grok`, or a
    // scenario this publish no longer carries, becomes what is on screen, so
    // copying the URL back out shares the view actually being shown. A bare
    // page URL stays bare: nothing was asked for. Users is rewritten even
    // when bare so ``/users/search/`` becomes ``/users/search``.
    if (hasParams(params) || page === "users") {
      writeParams(
        page,
        {
          user: params.user,
          q: params.q,
          post: params.post,
          from: params.from,
          expand: params.expand,
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
        setSelectedPost(params.post);
        setNeedle(params.q || "");
        setOrigin(params.from);
        setExpanded(params.expand);
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

  // Opening an author, or closing their page, stays on /users/search and is a
  // history entry of its own. The needle rides along, so closing lands back on
  // the results the author was opened from.
  const handleUserChange = (username: string | null) => {
    setSelectedUser(username);
    setSelectedPost(null);
    writeParams(page, { user: username, q: needle });
  };

  // Opening a post is a page of its own: `?user=&post=`, exactly the URL a
  // Search Tweets result links to. The needle is left out of it and comes back
  // from memory on close, so both ways in share one shareable address.
  // A post is its own page now, so a `?post=` on the Users page is a link
  // minted before that: forward it there rather than ignoring it. The router
  // is what knows `basePath`, so the redirect goes through it.
  useEffect(() => {
    if (page !== "users" || !selectedPost) return;
    router.replace(hrefFor("post", { post: selectedPost, user: selectedUser }));
  }, [router, page, selectedPost, selectedUser]);

  const handleExpandChange = (next: boolean) => {
    setExpanded(next);
    writeParams(page, {
      user: selectedUser,
      post: selectedPost,
      from: origin,
      q: needle,
      expand: next,
    });
    // Leaving the full view lands back at the top of what it was hiding.
    if (!next) window.scrollTo({ top: 0 });
  };

  // Submitting the Users search (Enter / clear) rewrites the current history
  // entry so Back still means "the previous page", not "the previous keystroke".
  const handleNeedleChange = (value: string) => {
    setNeedle(value);
    writeParams(
      page,
      { user: selectedUser, q: value, post: selectedPost },
      "replace",
    );
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
  // Posts subpages carries the filters over. The Users link means "go to the
  // search", so it keeps the needle but not the author currently open.
  const hrefOf = (target: PageKey) =>
    hrefFor(target, {
      q: needle,
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

  if (!data) {
    return <div className="status">Loading snapshots…</div>;
  }

  const snapshotWarning = error ? (
    <div className="status snapshot-warning">{error}</div>
  ) : null;

  const usersPage = (
    <UsersPage
      timezone={timezone}
      selected={selectedUser}
      onSelectUser={handleUserChange}
      selectedPost={selectedPost}
      needle={needle}
      onNeedleChange={handleNeedleChange}
      expanded={expanded}
      onExpandChange={handleExpandChange}
    />
  );

  const postPage = (
    <PostPage
      data={data.search}
      timezone={timezone}
      postId={selectedPost}
      username={selectedUser}
      from={origin}
      needle={needle}
      expanded={expanded}
      onExpandChange={handleExpandChange}
    />
  );

  // `?expand=1` on a detail view - a post, or an author - is that view and
  // nothing else: no rail, no tabs, no title bar. The Shell is not rendered at
  // all rather than hidden with CSS, so the full view carries none of its
  // weight. A listing has nothing to expand, so it ignores the flag.
  const fullView =
    expanded && (page === "post" || (page === "users" && selectedUser));
  if (fullView) {
    return (
      <div className="page-wrap page-full">
        {page === "post" ? postPage : usersPage}
      </div>
    );
  }

  // Which pages carry the Scenario / Query dropdowns is configured: the Users
  // page searches the whole graph, so they do not apply there.
  const showDataFilters = pageConfig(page).filters;

  return (
    <Shell
      page={page}
      hrefOf={hrefOf}
      activeUser={selectedUser}
      // The chip to mark active: a post on its page, else the author open.
      activeFavorite={
        page === "post"
          ? selectedPost && `p:${selectedPost}`
          : selectedUser && `u:${selectedUser}`
      }
      onOpenUser={handleUserChange}
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
      {snapshotWarning}
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
        {page === "tweets" ? (
          <TweetsPage
            data={data.search}
            timezone={timezone}
            needle={needle}
            onNeedleChange={handleNeedleChange}
          />
        ) : null}
        {page === "post" ? postPage : null}
        {page === "users" ? usersPage : null}
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
