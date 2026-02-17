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

function getResolvedApiUrl(defaultValue: string): string {
  return getRuntimeConfig()?.apiUrl || process.env.NEXUS_API_URL || process.env.NEXT_PUBLIC_API_URL || defaultValue;
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
  const env = runtimeEnv || process.env.NEXT_PUBLIC_NEXUS_ENV || process.env.NEXUS_ENV || 'local';
  
  if (!['local', 'cloudflare', 'staging'].includes(env)) {
    console.warn(`Unknown environment: ${env}, defaulting to 'local'`);
    return 'local';
  }
  
  return env as Environment;
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
