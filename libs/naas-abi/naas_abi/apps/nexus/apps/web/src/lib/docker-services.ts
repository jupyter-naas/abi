/**
 * Registry of docker-compose services that expose an embeddable web UI.
 *
 * URLs are built from a single shared host (PUBLIC_WEB_HOST) plus each
 * service's published port from `docker-compose.yml`, so there is no
 * per-service env var. Override the host via NEXT_PUBLIC_PUBLIC_WEB_HOST and
 * the scheme via NEXT_PUBLIC_WEB_PROTOCOL when reached behind a proxy.
 *
 * Services without a published host port (e.g. graph-explorer, only reachable
 * via Caddy) are intentionally omitted.
 */
export interface DockerService {
  id: string;
  label: string;
  description: string;
  url: string;
  /**
   * False when the service refuses to be rendered in an iframe (sends
   * `X-Frame-Options: DENY` / restrictive CSP `frame-ancestors`). The UI then
   * shows an "open in new tab" card instead of a blank embed. Defaults to true.
   */
  embeddable?: boolean;
}

// PUBLIC_WEB_HOST may carry a scheme, a path, or a port (e.g. 127.0.0.1:12688
// under `abi dev up`); reduce it to a bare hostname so we can append the
// fixed service ports below.
const WEB_HOST =
  (process.env.NEXT_PUBLIC_PUBLIC_WEB_HOST || 'localhost')
    .replace(/^https?:\/\//, '')
    .split('/')[0]
    .split(':')[0] || 'localhost';

const WEB_PROTOCOL = process.env.NEXT_PUBLIC_WEB_PROTOCOL || 'http';

const serviceUrl = (port: number, path = '') => `${WEB_PROTOCOL}://${WEB_HOST}:${port}${path}`;

export const DOCKER_SERVICES: DockerService[] = [
  {
    id: 'dagster',
    label: 'Dagster',
    description: 'Data pipeline orchestration & scheduling',
    url: serviceUrl(3001),
  },
  {
    id: 'fuseki',
    label: 'Fuseki',
    description: 'Triple store admin & SPARQL endpoint',
    url: serviceUrl(3030),
  },
  {
    id: 'qdrant',
    label: 'Qdrant',
    description: 'Vector store dashboard',
    url: serviceUrl(6333, '/dashboard'),
    embeddable: false, // sends X-Frame-Options: DENY
  },
  {
    id: 'minio',
    label: 'MinIO',
    description: 'Object storage console',
    url: serviceUrl(9001, '/login'),
    embeddable: false, // sends X-Frame-Options: DENY + restrictive CSP
  },
  {
    id: 'rabbitmq',
    label: 'RabbitMQ',
    description: 'Message bus management UI',
    url: serviceUrl(15672),
  },
  {
    id: 'redis-commander',
    label: 'Redis Commander',
    description: 'Redis key-value browser',
    url: serviceUrl(8082),
  },
  {
    id: 'streamlit',
    label: 'Streamlit',
    description: 'ABI Streamlit application',
    url: serviceUrl(8501),
  },
  {
    id: 'yasgui',
    label: 'YasGUI',
    description: 'SPARQL query editor',
    url: serviceUrl(3000),
  },
];
