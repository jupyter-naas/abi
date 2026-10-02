import {
  Activity,
  Boxes,
  Cpu,
  Database,
  FileText,
  GitBranch,
  HardDrive,
  History,
  KeyRound,
  Layers,
  Mail,
  Network,
  Table2,
  TerminalSquare,
  Waypoints,
  type LucideIcon,
} from 'lucide-react';
import { DOCKER_SERVICES, type DockerService } from '@/lib/docker-services';

/** A service from the `services:` section of config.yaml, as `GET /api/admin/services` returns it. */
export interface ConfiguredService {
  id: string;
  adapters: string[];
}

interface PlatformServiceInfo {
  label: string;
  description: string;
  icon: LucideIcon;
  /** Adapter → id of the docker service (lib/docker-services.ts) whose web UI manages it. */
  webUi?: Record<string, string>;
}

const PLATFORM_SERVICES: Record<string, PlatformServiceInfo> = {
  model_registry: { label: 'Model registry', description: 'Default chat and embedding models', icon: Cpu },
  secret: { label: 'Secrets', description: 'Where API keys and passwords are read from', icon: KeyRound },
  object_storage: {
    label: 'Object storage',
    description: 'Files, drives and datasets',
    icon: HardDrive,
    webUi: { s3: 'minio' },
  },
  triple_store: {
    label: 'Triple store',
    description: 'Knowledge graph (RDF) storage and SPARQL endpoint',
    icon: Network,
    webUi: { apache_jena_tdb2: 'fuseki' },
  },
  vector_store: {
    label: 'Vector store',
    description: 'Embeddings for semantic search',
    icon: Layers,
    webUi: { qdrant: 'qdrant' },
  },
  bus: {
    label: 'Message bus',
    description: 'Events between the API, agents and workers',
    icon: Waypoints,
    webUi: { rabbitmq: 'rabbitmq' },
  },
  kv: {
    label: 'Key-value store',
    description: 'Fast shared state: sessions, locks and cache',
    icon: Database,
    webUi: { redis: 'redis-commander' },
  },
  email: { label: 'Email', description: 'Outgoing email: invitations and notifications', icon: Mail },
  source_control: {
    label: 'Source control',
    description: 'Git repositories for apps and code',
    icon: GitBranch,
    webUi: { forgejo: 'forgejo' },
  },
  coding_environment: {
    label: 'Coding environment',
    description: 'Workspaces to edit and run code',
    icon: TerminalSquare,
    webUi: { coder: 'coder' },
  },
  document: { label: 'Documents', description: 'Document parsing and conversion', icon: FileText },
  dataset: { label: 'Datasets', description: 'Tabular datasets', icon: Table2 },
  activity_log: { label: 'Activity log', description: 'Record of user and agent actions', icon: History },
  event: { label: 'Events', description: 'Platform event store', icon: Activity },
  cache: { label: 'Cache', description: 'Hot and cold cache tiers', icon: Boxes },
};

export interface PlatformServiceRow {
  id: string;
  label: string;
  description: string;
  icon: LucideIcon;
  adapters: string[];
  /** The web UI that manages this service, when its adapter has one. */
  webUi?: DockerService;
}

function humanize(id: string): string {
  const words = id.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Label, icon, description and web UI for each configured service. */
export function describePlatformServices(services: ConfiguredService[]): PlatformServiceRow[] {
  return services.map(({ id, adapters }) => {
    const info = PLATFORM_SERVICES[id];
    const webUiId = adapters.map((adapter) => info?.webUi?.[adapter]).find(Boolean);
    return {
      id,
      label: info?.label ?? humanize(id),
      description: info?.description ?? '',
      icon: info?.icon ?? Boxes,
      adapters,
      webUi: DOCKER_SERVICES.find((service) => service.id === webUiId),
    };
  });
}
