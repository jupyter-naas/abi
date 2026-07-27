"use client";

import { useEffect, useMemo, useState } from "react";
import { Shell } from "@/components/Shell";
import { Filters } from "@/components/Filters";
import { CountPage } from "@/components/pages/CountPage";
import { ParametersPage } from "@/components/pages/ParametersPage";
import { SearchPage } from "@/components/pages/SearchPage";
import { loadSnapshots } from "@/lib/loadSnapshots";
import {
  readSessionTimezone,
  writeSessionTimezone,
} from "@/lib/session";
import type { PageKey, Snapshots } from "@/lib/types";

export default function Page() {
  const [data, setData] = useState<Snapshots | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<PageKey>("count");
  const [scenarioId, setScenarioId] = useState("");
  const [querySlug, setQuerySlug] = useState("");
  const [timezone, setTimezone] = useState("UTC");

  useEffect(() => {
    let cancelled = false;
    loadSnapshots()
      .then((snap) => {
        if (cancelled) return;
        setData(snap);
        setScenarioId(snap.scenarios[0]?.id || "");
        setQuerySlug(snap.queries[0]?.slug || "");
        const saved = readSessionTimezone();
        const allowed = new Set(snap.timezones.map((tz) => tz.id));
        if (saved && allowed.has(saved)) {
          setTimezone(saved);
        } else {
          setTimezone(snap.defaultTimezone || "UTC");
        }
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(
          `Failed to load snapshots: ${err.message}. Run the X app build to publish JSON under x/apps/x/.`,
        );
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleTimezoneChange = (id: string) => {
    setTimezone(id);
    writeSessionTimezone(id);
  };

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

  const showDataFilters = page === "count" || page === "search";

  return (
    <Shell
      page={page}
      onPageChange={setPage}
      builtAt={builtLabel}
      filters={
        showDataFilters ? (
          <Filters
            scenarios={data.scenarios}
            queries={data.queries}
            scenarioId={scenarioId}
            querySlug={querySlug}
            onScenarioChange={setScenarioId}
            onQueryChange={setQuerySlug}
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
        {page === "parameters" ? (
          <ParametersPage
            timezones={data.timezones}
            timezone={timezone}
            onTimezoneChange={handleTimezoneChange}
          />
        ) : null}
      </div>
    </Shell>
  );
}
