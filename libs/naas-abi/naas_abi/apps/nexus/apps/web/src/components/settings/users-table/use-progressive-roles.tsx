'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { readRoleChips, type RoleChip } from '@/components/people/role-chips';

/** How many people's Role one request reads (the API's limit). */
export const ROLES_BATCH = 100;

export type RolesBatch<R> = (principals: string[]) => Promise<Record<string, R[]>>;

export type ProgressiveRoles<R> = {
  /** Their Role once read; undefined while it is not (someone with no IAM id has none). */
  of: (principal: string | null | undefined) => R[] | undefined;
  /** What is read so far (principal -> their Role): changes with each batch. */
  found: Record<string, R[]>;
  /** The people of the page shown, read first: say it once the page is known. */
  show: (page: readonly (string | null | undefined)[]) => void;
  /** How many of the list's people have theirs read, of how many. */
  loaded: number;
  total: number;
  done: boolean;
  error: string | null;
};

/**
 * The Role of each person of a Users list read without it (`?roles=false`), a batch at a
 * time: first the people of the page shown (`show`, said while rendering, once the list is
 * searched, sorted and paged), then the others in the list's order (`all`). Paging on while
 * it reads moves the new page first. `generation` (a Reload) reads them all again; people
 * added to the list are read as they come.
 */
export function useProgressiveRoles<R>(
  all: readonly (string | null | undefined)[],
  fetchRoles: RolesBatch<R>,
  generation: number = 0
): ProgressiveRoles<R> {
  const [found, setFound] = useState<Record<string, R[]>>({});
  const [error, setError] = useState<string | null>(null);
  const allRef = useRef(all);
  const pageRef = useRef<readonly (string | null | undefined)[]>([]);
  useEffect(() => {
    allRef.current = all;
  }, [all]);
  // Read so far for this generation: kept when the list grows, dropped by a Reload.
  const read = useRef<{ generation: number; roles: Record<string, R[]> }>({ generation, roles: {} });
  const wanted = useMemo(() => [...new Set(all.filter((p): p is string => !!p))], [all]);
  const wantedKey = wanted.join('\n');

  useEffect(() => {
    if (read.current.generation !== generation) {
      read.current = { generation, roles: {} };
      setFound({});
    }
    const got = read.current.roles;
    let live = true;
    setError(null);
    void (async () => {
      while (live) {
        const pending = [...pageRef.current, ...allRef.current].filter(
          (p): p is string => !!p && !(p in got)
        );
        const batch = [...new Set(pending)].slice(0, ROLES_BATCH);
        if (batch.length === 0) return;
        try {
          const answer = await fetchRoles(batch);
          if (!live) return;
          for (const principal of batch) got[principal] = answer[principal] ?? [];
          setFound({ ...got });
        } catch (e) {
          if (live) setError(e instanceof Error ? e.message : 'Could not read their roles');
          return;
        }
      }
    })();
    return () => {
      live = false;
    };
  }, [fetchRoles, generation, wantedKey]);

  const loaded = wanted.filter((p) => p in found).length;
  return {
    of: (principal) => (principal ? found[principal] : []),
    found,
    show: (shown) => {
      pageRef.current = shown;
    },
    loaded,
    total: wanted.length,
    done: loaded >= wanted.length,
    error,
  };
}

/** Beside a Users list's search, while its people's Role is read: a search or a filter on
 *  Role sees only those read so far. */
export function RolesLoadingNote<R>({ roles }: { roles: ProgressiveRoles<R> }) {
  if (roles.error) {
    return (
      <p className="org-settings-users-filter-meta" role="alert" data-field="roles-loading">
        Roles could not be read: {roles.error}
      </p>
    );
  }
  if (roles.done || roles.total === 0) return null;
  return (
    <p className="org-settings-users-filter-meta" data-field="roles-loading">
      Roles loading {roles.loaded}/{roles.total}: a search or filter on Role sees those read so far.
    </p>
  );
}

/** Reads the Role of a batch of people from `url` (`GET <url>?principal=…`, a list's
 *  `…/roles` route): principal -> their Role. */
export function rolesBatchFrom(
  url: string,
  fetcher: (path: string, init?: RequestInit) => Promise<Response>
): RolesBatch<RoleChip> {
  return async (principals) => {
    const query = principals.map((p) => `principal=${encodeURIComponent(p)}`).join('&');
    const response = await fetcher(`${url}?${query}`);
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        if (typeof body?.detail === 'string') detail = body.detail;
      } catch {
        // no body
      }
      throw new Error(detail);
    }
    const body = (await response.json()) as Record<string, unknown>;
    return Object.fromEntries(Object.entries(body ?? {}).map(([principal, roles]) => [principal, readRoleChips(roles)]));
  };
}

/** A Role cell while it is read. */
export function RolesPending() {
  return <span className="inline-block h-4 w-28 animate-pulse bg-muted" aria-label="Loading roles" data-roles-pending="" />;
}
