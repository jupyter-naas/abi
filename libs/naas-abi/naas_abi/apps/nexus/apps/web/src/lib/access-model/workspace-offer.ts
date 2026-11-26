/**
 * A workspace's offer: what "<W> access" lists (S3, #1586). `GET` / `PUT
 * /api/workspaces/{id}/offer` cover its agents, apps, workflows and pipelines, by module (a
 * shared module offered whole is `<module>/*`); its features are General › Features'
 * (`/feature-access`, Everyone or Nobody). Everyone in "<W> workspace" reaches what it offers;
 * their level decides what they may do with it. Its Files part gives what lies outside the workspace
 * (Organization, Platform and System Files, `PUT /offer/files`), within each person's level. Its
 * Graphs part (the graphs it is given to read or write, every graph of its organization, what it
 * closes of its own) is Settings › Graphs' (`/resource-access/graphs`): the offer shows its summary.
 * Its Models part names the chat models it uses (`*`: every model its people's model sets allow) and
 * the default an agent on a model it does not offer switches to (`PUT /offer/models`).
 * Its Maps part (the platform's feeds and basemaps it uses, those other workspaces share with it) is
 * Settings › Maps' (`/api/maps/permissions`): the offer shows its summary too.
 * Its ontology files (`ontologies`) are switched here (`PUT /offer/ontologies`) as in Settings ›
 * Ontologies: an organization's admins add one, a workspace admin may take one back.
 */
import { authFetch } from '@/stores/auth';

export type OfferKind = 'agents' | 'apps' | 'workflows' | 'pipelines';

export const OFFER_KINDS: { kind: OfferKind; label: string; type: string }[] = [
  { kind: 'agents', label: 'Agents', type: 'agent' },
  { kind: 'apps', label: 'Apps', type: 'app' },
  { kind: 'workflows', label: 'Workflows', type: 'workflow' },
  { kind: 'pipelines', label: 'Pipelines', type: 'pipeline' },
];

/** The item name that offers a module whole. */
export const WHOLE_MODULE = '*';

export type OfferItem = { module: string; name: string };

export type OfferState = {
  workspace_id: string;
  scope: string;
  /** "<W> access"; null for a workspace that has none yet. */
  access_policy: { id: string; name: string; owner_scope: string } | null;
  /** IAM lets the caller update "<W> access". */
  editable: boolean;
  whole_module: string;
  offered: Record<OfferKind, OfferItem[]> & {
    /** The sources of the search it offers: a feature (`chat`...) or `web.<engine>`. */
    search_sources?: string[];
  };
  /** The files it gives outside it; no Organization Files row for a workspace in no organization. */
  files?: FileRow[];
  my_files?: MyFiles;
  /** The Graphs part, as Settings › Graphs edits it: shown here, not changed. */
  graphs?: GraphsSummary;
  /** The Models part: the chat models it uses and its default. */
  models?: ModelsPart;
  /** The Maps part, as Settings › Maps edits it: shown here, not changed. */
  maps?: MapsSummary;
};

/** The model naming every model (the people's model sets decide which). */
export const EVERY_MODEL = '*';

/** The chat models a workspace uses, its default, and those the caller may pick from. */
export type ModelsPart = {
  /** `['*']` for every model, else the canonical ids it uses. */
  offered: string[];
  /** What an agent on a model it does not offer switches to; required for a list. */
  default: string | null;
  every: boolean;
  /** The chat models the caller may list. */
  available: string[];
};

/** The setting after a change: every model, or a list that keeps a default among it. */
export function modelsAfter(
  part: ModelsPart,
  change: { every: true } | { every: false } | { model: string; on: boolean } | { default: string },
): { models: string[]; default: string | null } {
  if ('every' in change && change.every) return { models: [EVERY_MODEL], default: null };
  const current = part.every ? [] : part.offered;
  if ('every' in change) {
    const first = part.default ?? part.available[0] ?? null;
    return first ? { models: [first], default: first } : { models: [EVERY_MODEL], default: null };
  }
  if ('default' in change) return { models: current, default: change.default };
  const models = change.on ? [...new Set([...current, change.model])].sort() : current.filter((m) => m !== change.model);
  const kept = part.default && models.includes(part.default) ? part.default : (models[0] ?? null);
  return { models, default: kept };
}
  /** The ontology files it offers; null where the deployment has no ontology. */
  ontologies?: OfferOntologies | null;
};

/** An ontology file of the deployment, as the offer names it; or a ref no file answers to. */
export type OntologyRow = {
  /** Its id in the catalog (`core:bfo.ttl`), what a change names. */
  id: string;
  label: string;
  module: string | null;
  offered: boolean;
  /** False: a ref of the offer no file of the deployment answers to (removable). */
  available: boolean;
  /** The caller may assign it here (`nexus:AssignOntology` in the workspace's organization). */
  assignable: boolean;
  editable: boolean;
  reason: string | null;
};

/** The Ontologies part: the offer's refs as written, a row per file, or why they are not listed. */
export type OfferOntologies = { offered: string[]; rows: OntologyRow[]; error: string | null };

/** What the offer gives of the graphs outside the workspace, and closes of its own. */
export type GraphsSummary = {
  /** Graphs given to read (those given to write included). */
  read: number;
  /** Graphs given to write (a Viewer still only reads). */
  write: number;
  /** Every graph of its organization, the ones made later included. */
  read_all: boolean;
  /** Its own graphs are offered (false: excluded). */
  include_owned: boolean;
  /** Its members may create graphs. */
  allow_create: boolean;
};

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** The Graphs part in words, one line each. */
export function graphsSummaryLines(graphs: GraphsSummary): string[] {
  const lines = [
    graphs.read === 0
      ? 'No graph of another workspace or of the platform is given.'
      : `${plural(graphs.read, 'graph', 'graphs')} given to read, ${graphs.write} of them to write.`,
  ];
  if (graphs.read_all) lines.push('Every graph of its organization is read, the ones made later too.');
  if (!graphs.include_owned) lines.push('Its own graphs are excluded.');
  if (!graphs.allow_create) lines.push('Creating graphs is closed.');
  return lines;
}

/** Where the Graphs part is changed. */
export const graphsSettingsHref = (workspaceId: string) =>
  `/workspace/${encodeURIComponent(workspaceId)}/settings/graphs`;

/** What the offer gives of one kind of Maps item the workspace does not own. */
export type MapsKindSummary = {
  /** Every one of the platform, the ones added later too. */
  every: boolean;
  /** Those of the platform given by name. */
  named: number;
  /** Those of the platform it does not use, though every one is given. */
  closed: number;
  /** Those other workspaces share with it. */
  shared: number;
};

/** The Maps part: the platform's feeds and basemaps it uses, and those shared with it. */
export type MapsSummary = { feeds: MapsKindSummary; basemaps: MapsKindSummary };

function mapsKindLines(kind: MapsKindSummary, one: string, many: string): string[] {
  const lines: string[] = [];
  if (kind.every) lines.push(`Every ${one} of the platform, the ones added later too.`);
  else if (kind.named > 0) lines.push(`${plural(kind.named, one, many)} of the platform.`);
  else lines.push(`No ${one} of the platform.`);
  if (kind.every && kind.closed > 0) lines.push(`${plural(kind.closed, one, many)} of the platform not used here.`);
  if (kind.shared > 0) lines.push(`${plural(kind.shared, one, many)} shared by other workspaces.`);
  return lines;
}

/** The Maps part in words, one line each: its feeds, then its basemaps. */
export function mapsSummaryLines(maps: MapsSummary): string[] {
  return [...mapsKindLines(maps.feeds, 'map feed', 'map feeds'), ...mapsKindLines(maps.basemaps, 'basemap', 'basemaps')];
}

/** Where the Maps part is changed (Settings › Maps, each item's Access). */
export const mapsSettingsHref = (workspaceId: string) =>
  `/workspace/${encodeURIComponent(workspaceId)}/settings/maps`;

export type OfferChange = { kind: OfferKind; module: string; name: string; offered: boolean };

/** What a file section gives: nothing, reading, or reading and writing (a Viewer still only reads). */
export type FileMode = 'off' | 'read' | 'write';
export type FileKey = 'org_files' | 'platform_files' | 'system_files';

/** A section of files the workspace gives outside it (`GivenOrgFiles`...). */
export type FileRow = {
  key: FileKey;
  label: string;
  mode: FileMode;
  /** Every mode the section has (System Files: Off and Read). */
  modes: FileMode[];
  /** The modes the caller may choose: those they hold, and any narrower than the current one. */
  choices: FileMode[];
  editable: boolean;
  reason: string | null;
};

/** My Files: a setting of the deployment, not of the workspace. */
export type MyFiles = { members: 'write'; viewers: 'read' | 'none' };

export class OfferError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'OfferError';
    this.status = status;
  }
}

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

async function failure(response: Response, fallback: string): Promise<OfferError> {
  let detail = '';
  try {
    const raw = (await response.json())?.detail;
    if (typeof raw === 'string') detail = raw;
    else if (Array.isArray(raw) && raw[0]?.msg) detail = String(raw[0].msg);
  } catch {
    // no JSON body
  }
  if (!detail && response.status === 403) detail = 'You may not change what this workspace offers.';
  return new OfferError(detail || fallback, response.status);
}

export function createOfferApi(fetcher: Fetcher = authFetch) {
  const path = (workspaceId: string) => `/api/workspaces/${encodeURIComponent(workspaceId)}/offer`;
  return {
    read: async (workspaceId: string): Promise<OfferState> => {
      const response = await fetcher(path(workspaceId));
      if (!response.ok) throw await failure(response, `Could not read the workspace's offer (HTTP ${response.status}).`);
      return (await response.json()) as OfferState;
    },
    /** One write of "<W> access": every change or none (403, 422 name why). */
    save: async (workspaceId: string, changes: OfferChange[]): Promise<OfferState> => {
      const response = await fetcher(path(workspaceId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes }),
      });
      if (!response.ok) throw await failure(response, `Could not save the offer (HTTP ${response.status}).`);
      return (await response.json()) as OfferState;
    },
    /** Offer or stop offering sources of the search, in one write of "<W> access". */
    saveSearchSources: async (workspaceId: string, changes: Record<string, boolean>): Promise<OfferState> => {
      const response = await fetcher(`${path(workspaceId)}/search-sources`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes }),
      });
      if (!response.ok) throw await failure(response, `Could not save the search sources (HTTP ${response.status}).`);
      return (await response.json()) as OfferState;
    },
    /** The chat models the workspace uses (`['*']`: every one) and its default model. */
    saveModels: async (workspaceId: string, models: string[], defaultModel: string | null): Promise<OfferState> => {
      const response = await fetcher(`${path(workspaceId)}/models`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models, default: defaultModel }),
      });
      if (!response.ok) throw await failure(response, `Could not save the models (HTTP ${response.status}).`);
      return (await response.json()) as OfferState;
    },
    /** Give (or stop giving) files outside the workspace, in one write of "<W> access". */
    saveFiles: async (workspaceId: string, changes: Partial<Record<FileKey, FileMode>>): Promise<OfferState> => {
      const response = await fetcher(`${path(workspaceId)}/files`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(changes),
      });
      if (!response.ok) throw await failure(response, `Could not save the files (HTTP ${response.status}).`);
      return (await response.json()) as OfferState;
    },
    /** Offer or stop offering ontology files (`{row id: offered}`), in one write of "<W> access". */
    saveOntologies: async (workspaceId: string, changes: Record<string, boolean>): Promise<OfferState> => {
      const response = await fetcher(`${path(workspaceId)}/ontologies`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes }),
      });
      if (!response.ok) throw await failure(response, `Could not save the ontologies (HTTP ${response.status}).`);
      return (await response.json()) as OfferState;
    },
  };
}

export type OfferApi = ReturnType<typeof createOfferApi>;
