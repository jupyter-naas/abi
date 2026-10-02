'use client';

/** Explorer state and the calls behind it. Components render; this hook decides. */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { DataApi, Failure, Result } from './data-api';
import { ROOT_CRUMB, appendPage, filterEntries, openOnPath, type Crumb, type Location } from './data-model';
import type { AuditEntry, ResourceDetail, ResourceEntry, ResourceServiceInfo } from './data-types';

const PAGE = 100;
const SEARCH_DELAY_MS = 300;

export interface Explorer {
  services: ResourceServiceInfo[] | null;
  servicesFailure: Failure | null;
  service: ResourceServiceInfo | null;
  path: Crumb[];
  parent: string;
  /** Loaded entries, filtered by the search text. */
  entries: ResourceEntry[] | null;
  loadedCount: number;
  hasMore: boolean;
  listable: boolean;
  listFailure: Failure | null;
  loadingMore: boolean;
  search: string;
  selected: string | null;
  detail: ResourceDetail | null;
  detailFailure: Failure | null;
  detailLoading: boolean;
  /** When the revealed value hides again (epoch ms), or null. */
  revealedUntil: number | null;
  revealing: boolean;

  selectService: (name: string) => void;
  /** Another service's entry (or its root when ``item`` is null). */
  goTo: (name: string, item: string | null) => void;
  open: (crumb: Crumb) => void;
  up: () => void;
  openItem: (id: string) => Promise<void>;
  closeItem: () => void;
  select: (id: string | null) => void;
  setSearch: (text: string) => void;
  loadMore: () => void;
  refresh: () => void;
  reveal: (seconds: number) => Promise<Failure | null>;
  hide: () => void;
  download: (id: string) => Promise<Result<Blob>>;
  write: (id: string, body: Blob | string, confirm?: string) => Promise<Result<ResourceEntry>>;
  remove: (id: string, confirm: string) => Promise<Result<null>>;
  history: (id: string) => Promise<Result<{ entries: AuditEntry[] }>>;
}

export function useExplorer(api: DataApi, initial: Location, nonce = 0): Explorer {
  const [services, setServices] = useState<ResourceServiceInfo[] | null>(null);
  const [servicesFailure, setServicesFailure] = useState<Failure | null>(null);
  const [serviceName, setServiceName] = useState<string | null>(initial.service);
  const [path, setPath] = useState<Crumb[]>(initial.path);
  const [loaded, setLoaded] = useState<ResourceEntry[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [listable, setListable] = useState(true);
  const [listFailure, setListFailure] = useState<Failure | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [search, setSearchText] = useState('');
  const [serverQuery, setServerQuery] = useState('');
  const [selected, setSelected] = useState<string | null>(initial.item);
  const [detail, setDetail] = useState<ResourceDetail | null>(null);
  const [detailFailure, setDetailFailure] = useState<Failure | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [revealedUntil, setRevealedUntil] = useState<number | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [reloads, setReloads] = useState(0);
  const pendingItem = useRef<string | null>(initial.item);
  const listToken = useRef(0);

  const service = useMemo(
    () => services?.find((s) => s.name === serviceName) ?? null,
    [services, serviceName],
  );
  const parent = path[path.length - 1].id;

  useEffect(() => {
    let cancelled = false;
    void api.services().then((result) => {
      if (cancelled) return;
      if (!result.ok) {
        setServicesFailure(result);
        return;
      }
      setServicesFailure(null);
      setServices(result.data.services);
      setServiceName((current) => {
        if (current && result.data.services.some((s) => s.name === current)) return current;
        return result.data.services.find((s) => s.available)?.name ?? null;
      });
    });
    return () => {
      cancelled = true;
    };
  }, [api, nonce]);

  // Server-side search only where the service supports it; the text filters loaded pages at once.
  useEffect(() => {
    if (!service?.capabilities.search) return;
    const timer = window.setTimeout(() => setServerQuery(search.trim()), SEARCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [search, service?.capabilities.search]);

  const fetchPage = useCallback(
    async (after: string | null) => {
      if (!service) return;
      const token = ++listToken.current;
      const result = await api.list(service.name, parent, {
        cursor: after,
        limit: PAGE,
        query: service.capabilities.search ? serverQuery || null : null,
      });
      if (token !== listToken.current) return;
      if (!result.ok) {
        setListFailure(result);
        if (!after) setLoaded([]);
        return;
      }
      setListFailure(null);
      setListable(result.data.listable !== false);
      setLoaded((prev) => (after && prev ? appendPage(prev, result.data.entries) : result.data.entries));
      setCursor(result.data.next_cursor);
    },
    [api, service, parent, serverQuery],
  );

  useEffect(() => {
    if (!service?.available) return;
    if (!service.capabilities.browse && !service.capabilities.lookup) {
      setLoaded([]);
      setCursor(null);
      return;
    }
    setLoaded(null);
    setCursor(null);
    void fetchPage(null);
  }, [service?.available, service?.capabilities.browse, service?.capabilities.lookup, fetchPage, nonce, reloads]);

  const openItem = useCallback(
    async (id: string) => {
      if (!service) return;
      setSelected(id);
      setDetailLoading(true);
      setDetailFailure(null);
      setRevealedUntil(null);
      const result = await api.read(service.name, id);
      setDetailLoading(false);
      if (result.ok) setDetail(result.data);
      else {
        setDetail(null);
        setDetailFailure(result);
      }
    },
    [api, service],
  );

  // A deep link names an item: open it once the service is known.
  useEffect(() => {
    if (!service?.available || !pendingItem.current) return;
    const id = pendingItem.current;
    pendingItem.current = null;
    void openItem(id);
  }, [service, openItem]);

  // A revealed value hides itself again.
  useEffect(() => {
    if (revealedUntil === null) return;
    const timer = window.setTimeout(() => {
      setRevealedUntil(null);
      setDetail((d) =>
        d && d.content?.encoding !== 'masked'
          ? { ...d, content: { encoding: 'masked', text: null, size: null, truncated: false }, view: null }
          : d,
      );
    }, Math.max(0, revealedUntil - Date.now()));
    return () => window.clearTimeout(timer);
  }, [revealedUntil]);

  const closeItem = useCallback(() => {
    setDetail(null);
    setDetailFailure(null);
    setDetailLoading(false);
    setRevealedUntil(null);
  }, []);

  const resetListing = () => {
    closeItem();
    setSelected(null);
    setSearchText('');
    setServerQuery('');
  };

  const selectService = (name: string) => {
    if (name === serviceName) return;
    resetListing();
    setPath([ROOT_CRUMB]);
    setServiceName(name);
  };

  const goTo = (name: string, item: string | null) => {
    resetListing();
    setPath([ROOT_CRUMB]);
    if (name === serviceName) {
      if (item) void openItem(item);
      else setReloads((n) => n + 1);
      return;
    }
    pendingItem.current = item;
    setServiceName(name);
  };

  const open = (crumb: Crumb) => {
    resetListing();
    setPath((current) => openOnPath(current, crumb));
  };

  const up = () => {
    if (path.length <= 1) return;
    resetListing();
    setPath(path.slice(0, -1));
  };

  const refresh = () => {
    setReloads((n) => n + 1);
    if (detail) void openItem(detail.entry.id);
  };

  const loadMore = () => {
    if (!cursor || loadingMore) return;
    setLoadingMore(true);
    void fetchPage(cursor).finally(() => setLoadingMore(false));
  };

  const reveal = async (seconds: number): Promise<Failure | null> => {
    if (!service || !detail) return null;
    setRevealing(true);
    const result = await api.reveal(service.name, detail.entry.id);
    setRevealing(false);
    if (!result.ok) return result;
    setDetail(result.data);
    setRevealedUntil(Date.now() + seconds * 1000);
    return null;
  };

  const hide = () => {
    setRevealedUntil(Date.now());
  };

  const write = async (id: string, body: Blob | string, confirm?: string) => {
    if (!service) return { ok: false, status: 0, reason: 'No service selected' } as Failure;
    const result = await api.write(service.name, id, body, confirm);
    if (result.ok) {
      setReloads((n) => n + 1);
      // Some writes leave nothing to read (mail sent through an adapter that keeps no copy).
      if (result.data.actions.includes('read')) await openItem(result.data.id);
    }
    return result;
  };

  const remove = async (id: string, confirm: string) => {
    if (!service) return { ok: false, status: 0, reason: 'No service selected' } as Failure;
    const result = await api.remove(service.name, id, confirm);
    if (result.ok) {
      if (detail?.entry.id === id) closeItem();
      if (selected === id) setSelected(null);
      setLoaded((prev) => prev?.filter((e) => e.id !== id) ?? prev);
      setReloads((n) => n + 1);
    }
    return result;
  };

  const entries = useMemo(() => (loaded ? filterEntries(loaded, search) : null), [loaded, search]);

  return {
    services,
    servicesFailure,
    service,
    path,
    parent,
    entries,
    loadedCount: loaded?.length ?? 0,
    hasMore: cursor !== null,
    listable,
    listFailure,
    loadingMore,
    search,
    selected,
    detail,
    detailFailure,
    detailLoading,
    revealedUntil,
    revealing,
    selectService,
    goTo,
    open,
    up,
    openItem,
    closeItem,
    select: setSelected,
    setSearch: setSearchText,
    loadMore,
    refresh,
    reveal,
    hide,
    download: (id: string) =>
      service ? api.download(service.name, id) : Promise.resolve({ ok: false, status: 0, reason: 'No service' }),
    write,
    remove,
    history: (id: string) =>
      service ? api.history(service.name, id) : Promise.resolve({ ok: false, status: 0, reason: 'No service' }),
  };
}
