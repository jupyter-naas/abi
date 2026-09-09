/**
 * Registry of docker-compose services that expose a web UI, embedded under
 * Settings > Services.
 *
 * Host resolution: NEXT_PUBLIC_PUBLIC_WEB_HOST wins when set; otherwise the
 * host actually used to reach Nexus is reused (the browser's hostname),
 * so production traffic resolves to the real service IP/domain instead of
 * falling back to localhost. The port comes from each service's published
 * docker-compose port; there is no per-service host override.
 *
 * Services without a published host port (e.g. graph-explorer, only reachable
 * via Caddy) are intentionally omitted.
 *
 * Services that need a login (RabbitMQ, Fuseki) are not auto-authenticated:
 * their credentials live in .env but aren't passed into the nexus-web
 * container's environment, and the browser can't reach the Python API from
 * inside that container to broker them either. Auto-login would need that
 * plumbing added in docker-compose.yml first, so for now these just show
 * their normal login screen.
 */
export interface DockerService {
  id: string;
  label: string;
  description: string;
  port: number;
  path?: string;
  /**
   * False when the service refuses to be rendered in an iframe (sends
   * X-Frame-Options: DENY / restrictive CSP frame-ancestors). The UI then
   * shows an "open in new tab" card instead of a blank embed. Defaults to true.
   */
  embeddable?: boolean;
}

export const DOCKER_SERVICES: DockerService[] = [
  {
    id: 'dagster',
    label: 'Dagster',
    description: 'Data pipeline orchestration & scheduling',
    port: 3001,
  },
  {
    id: 'fuseki',
    label: 'Fuseki',
    description: 'Triple store admin & SPARQL endpoint',
    port: 3030,
  },
  {
    id: 'qdrant',
    label: 'Qdrant',
    description: 'Vector store dashboard',
    port: 6333,
    path: '/dashboard',
    embeddable: false, // sends X-Frame-Options: DENY
  },
  {
    id: 'minio',
    label: 'MinIO',
    description: 'Object storage console',
    port: 9001,
    path: '/login',
    embeddable: false, // sends X-Frame-Options: DENY + restrictive CSP
  },
  {
    id: 'rabbitmq',
    label: 'RabbitMQ',
    description: 'Message bus management UI',
    port: 15672,
  },
  {
    id: 'redis-commander',
    label: 'Redis Commander',
    description: 'Redis key-value browser',
    port: 8082,
  },
  {
    id: 'streamlit',
    label: 'Streamlit',
    description: 'ABI Streamlit application',
    port: 8501,
  },
  {
    id: 'yasgui',
    label: 'YasGUI',
    description: 'SPARQL query editor',
    port: 3000,
  },
];

/**
 * Bare hostname Nexus is actually being reached on right now, so service
 * links resolve correctly in production instead of defaulting to localhost.
 *
 * Order: explicit override, then the browser's own hostname, then localhost
 * as a last resort for contexts with neither (server-side rendering, local
 * tooling).
 */
export function resolveServiceHost(): string {
  const explicit = process.env.NEXT_PUBLIC_PUBLIC_WEB_HOST;
  const raw = explicit || (typeof window !== 'undefined' ? window.location.hostname : null) || 'localhost';
  return (
    raw
      .replace(/^https?:\/\//, '')
      .split('/')[0]
      .split(':')[0] || 'localhost'
  );
}

/** Build a service's URL against the currently reachable host. */
export function buildServiceUrl(service: DockerService, host: string, protocol?: string): string {
  const resolvedProtocol = protocol || process.env.NEXT_PUBLIC_WEB_PROTOCOL || 'http';
  return `${resolvedProtocol}://${host}:${service.port}${service.path ?? ''}`;
}
