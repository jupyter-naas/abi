/**
 * Environment-aware configuration for NEXUS frontend.
 * 
 * In local dev: reads from environment variables set by Next.js
 * In Cloudflare: reads from environment bindings
 */

export type Environment = 'local' | 'cloudflare' | 'staging';

export interface NexusConfig {
  env: Environment;
  name: string;
  appName: string;
  version: string;
  
  // URLs
  frontendUrl: string;
  apiUrl: string;
  websocketPath: string;
  ollamaUrl: string;
  
  // Features
  features: {
    enableGraph: boolean;
    enableOntology: boolean;
    enableLab: boolean;
    enableApps: boolean;
  };
  
  // Providers
  providers: {
    ollama: { enabled: boolean };
    cloudflare: { enabled: boolean };
    anthropic: { enabled: boolean };
    openai: { enabled: boolean };
  };
}

declare global {
  interface Window {
    __NEXUS_RUNTIME_CONFIG__?: {
      apiUrl?: string;
      env?: Environment;
      websocketPath?: string;
      frontendUrl?: string;
      ollamaUrl?: string;
    };
  }
}

function getRuntimeConfig() {
  if (typeof window === 'undefined') {
    return undefined;
  }

  return window.__NEXUS_RUNTIME_CONFIG__;
}

/** True when the page is served from a public host (not loopback / *.localhost). */
function isBrowserPublicOrigin(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  const host = window.location.hostname;
  return host !== 'localhost' && host !== '127.0.0.1' && !host.endsWith('.localhost');
}

/**
 * Last-resort API URL when runtime-config and NEXT_PUBLIC_* are missing on a
 * public origin. Matches Nexus hostname convention: api.<frontend-host>.
 */
function derivePublicApiUrl(): string {
  const { protocol, hostname } = window.location;
  return `${protocol}//api.${hostname}`;
}

function getResolvedApiUrl(defaultValue: string): string {
  const runtimeUrl = getRuntimeConfig()?.apiUrl;
  if (runtimeUrl) {
    return runtimeUrl;
  }

  const envUrl = process.env.NEXUS_API_URL || process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) {
    return envUrl;
  }

  // Next.js can evaluate client modules before /runtime-config.js runs. On a
  // public origin, never use loopback or another product's baked default
  // (e.g. api.other.example.com while serving app.example.com).
  if (isBrowserPublicOrigin()) {
    const derived = derivePublicApiUrl();
    if (defaultValue !== derived) {
      console.warn(
        `Nexus apiUrl missing at runtime on ${window.location.origin}; using ${derived} instead of ${defaultValue}.`
      );
    }
    return derived;
  }

  return defaultValue;
}

function getResolvedWebsocketPath(defaultValue: string): string {
  return getRuntimeConfig()?.websocketPath || process.env.NEXT_PUBLIC_WS_PATH || defaultValue;
}

function getResolvedFrontendUrl(defaultValue: string): string {
  return getRuntimeConfig()?.frontendUrl || process.env.NEXT_PUBLIC_FRONTEND_URL || defaultValue;
}

function getResolvedOllamaUrl(defaultValue: string): string {
  return getRuntimeConfig()?.ollamaUrl || process.env.NEXT_PUBLIC_OLLAMA_URL || defaultValue;
}

/**
 * Get current environment from NEXT_PUBLIC_NEXUS_ENV or NEXUS_ENV
 */
export function getEnvironment(): Environment {
  const runtimeEnv = getRuntimeConfig()?.env;
  const env = runtimeEnv || process.env.NEXT_PUBLIC_NEXUS_ENV || process.env.NEXUS_ENV;

  if (env && ['local', 'cloudflare', 'staging'].includes(env)) {
    return env as Environment;
  }

  if (env) {
    console.warn(`Unknown environment: ${env}, defaulting to 'local'`);
  }

  // Public hosts should not inherit the local defaults (localhost:9879 API).
  if (isBrowserPublicOrigin()) {
    return 'cloudflare';
  }

  return 'local';
}

/**
 * Environment-specific configurations
 */
const configs: Record<Environment, NexusConfig> = {
  local: {
    env: 'local',
    name: 'Local Development',
    appName: 'NEXUS',
    version: '0.1.0',
    frontendUrl: 'http://localhost:3000',
    apiUrl: 'http://localhost:9879',
    websocketPath: '/ws/socket.io',
    ollamaUrl: 'http://localhost:11434',
    features: {
      enableGraph: true,
      enableOntology: true,
      enableLab: true,
      enableApps: false,
    },
    providers: {
      ollama: { enabled: true },
      cloudflare: { enabled: true },
      anthropic: { enabled: false },
      openai: { enabled: false },
    },
  },
  
  cloudflare: {
    env: 'cloudflare',
    name: 'Cloudflare Production',
    appName: 'NEXUS',
    version: '0.1.0',
    frontendUrl: 'https://nexus.naas.ai',
    apiUrl: 'https://api.nexus.naas.ai',
    websocketPath: '/ws/socket.io',
    ollamaUrl: '',  // No local Ollama in cloud
    features: {
      enableGraph: true,
      enableOntology: true,
      enableLab: true,
      enableApps: false,
    },
    providers: {
      ollama: { enabled: false },  // No local Ollama in cloud
      cloudflare: { enabled: true },
      anthropic: { enabled: true },
      openai: { enabled: true },
    },
  },
  
  staging: {
    env: 'staging',
    name: 'Staging',
    appName: 'NEXUS',
    version: '0.1.0',
    frontendUrl: 'https://staging.nexus.naas.ai',
    apiUrl: 'https://api.staging.nexus.naas.ai',
    websocketPath: '/ws/socket.io',
    ollamaUrl: '',  // No local Ollama in staging
    features: {
      enableGraph: true,
      enableOntology: true,
      enableLab: true,
      enableApps: false,
    },
    providers: {
      ollama: { enabled: false },
      cloudflare: { enabled: true },
      anthropic: { enabled: true },
      openai: { enabled: false },
    },
  },
};

/**
 * Get configuration for current or specified environment
 */
export function getConfig(env?: Environment): NexusConfig {
  const environment = env || getEnvironment();
  const config = configs[environment];

  return {
    ...config,
    frontendUrl: getResolvedFrontendUrl(config.frontendUrl),
    apiUrl: getResolvedApiUrl(config.apiUrl),
    websocketPath: getResolvedWebsocketPath(config.websocketPath),
    ollamaUrl: getResolvedOllamaUrl(config.ollamaUrl),
  };
}

/**
 * Check if running in local development
 */
export function isLocal(): boolean {
  return getEnvironment() === 'local';
}

/**
 * Check if running on Cloudflare
 */
export function isCloudflare(): boolean {
  return getEnvironment() === 'cloudflare';
}

/**
 * Check if a feature is enabled
 */
export function isFeatureEnabled(feature: keyof NexusConfig['features']): boolean {
  const config = getConfig();
  return config.features[feature];
}

/**
 * Get API base URL
 */
export function getApiUrl(): string {
  return getConfig().apiUrl;
}

/**
 * Get Socket.IO endpoint path
 */
export function getWebsocketPath(): string {
  return getConfig().websocketPath;
}

/**
 * Get default Ollama endpoint URL
 */
export function getOllamaUrl(): string {
  return getConfig().ollamaUrl;
}

// Default export for convenience
const config = getConfig();
export default config;
