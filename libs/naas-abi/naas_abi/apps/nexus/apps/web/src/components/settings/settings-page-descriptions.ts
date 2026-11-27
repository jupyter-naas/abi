/**
 * What each page of Settings is for, in a few words: the hover tip of its link in the Settings
 * column (`SettingsLevelsNav`), and the description under the title of the pages that have one.
 * One place for the texts, so the same page reads the same at every level. Short fragments,
 * no final period, as the dock's tips.
 */
import { SYSTEM_VIEWS } from '@/app/settings/system/system-tabs';

/** A workspace's pages, by link (`/settings/<page>`). */
export const WORKSPACE_PAGE_DESCRIPTIONS: Record<string, string> = {
  '/settings/general': 'Name, slug, group and wallpaper of this workspace',
  '/settings/users': 'The members of this workspace and their role',
  '/settings/groups': 'Groups of people, to give rights to many at once',
  '/settings/analytics': 'How members use this workspace',
  '/settings/policies': 'The policies that decide who may do what here',
  '/settings/features': 'The Nexus features a policy grants, and up to which level',
  '/settings/core-services': 'How far people go with each engine service: graphs, files, vectors…',
  '/settings/modules': 'What a policy grants of each module: its agents, apps and workflows',
  '/settings/agents': 'The agents you may use here, and those this workspace builds',
  '/settings/apps': 'The module apps you may open here',
  '/settings/datasets': 'The dataset namespaces this workspace uses',
  '/settings/files': 'The files and drives this workspace uses',
  '/settings/graphs': 'The knowledge graphs this workspace reads and writes',
  '/settings/maps': 'The feeds and layers drawn on Maps',
  '/settings/models': 'The chat models used here, and the default one',
  '/settings/ontologies': 'The ontologies available in this workspace',
  '/settings/search': 'What Search looks into: its sources and topics',
  '/settings/skills': 'Reusable prompts, run in the chat with /<slug>',
  '/settings/workflows': 'The module workflows and pipelines of this workspace',
};

/** An organization's pages, by slug. */
export const ORGANIZATION_PAGE_DESCRIPTIONS: Record<string, string> = {
  general: 'Name and identity of the organization',
  branding: 'Logos and colours of the organization',
  workspaces: 'The workspaces of this organization',
  users: 'The members of the organization and their role',
  groups: 'Groups of people, to give rights to many at once',
  analytics: 'How members use the organization’s workspaces',
  policies: 'The policies that decide who may do what, here and in its workspaces',
  features: 'The Nexus features its workspaces may offer, and up to which level',
  'core-services': 'How far people go with each engine service, in every workspace',
  modules: 'What its workspaces may offer of each module',
  domains: 'The email domains of the organization',
  servers: 'The servers of the organization',
  services: 'Platform services with a web UI',
  billing: 'Plan and invoices',
};

/** Another organization's link, under "Other organizations". */
export const OTHER_ORGANIZATION_DESCRIPTION = 'Open the settings of this organization';

const SERVICE_DESCRIPTIONS: Record<string, string> = {
  discovery: 'Modules found on the network, and their endpoints',
  bus: 'Messages between the engine’s services',
  event: 'The events the platform stores',
  activity_log: 'Who did what, call by call',
  model_registry: 'Model providers and the models they serve',
  secret: 'The secrets modules use',
  email: 'The email service and what it sent',
  source_control: 'The repositories connected to the platform',
  coding_environment: 'Remote coding environments',
  triple_store: 'The triple store and its graphs',
  vector_store: 'Collections of embeddings',
  document: 'The document store and its collections',
  dataset: 'The dataset store and its namespaces',
  object_storage: 'Buckets and files of the object store',
  keyvalue: 'Keys of the key-value store',
  cache: 'What the engine keeps in cache',
};

/** The platform's pages, by item id (`app/settings/lib/nav.ts`). */
export const PLATFORM_PAGE_DESCRIPTIONS: Record<string, string> = {
  general: 'Name and identity every organization shares',
  theme: 'Every component of the design kit, in its states',
  organizations: 'Every organization on the platform',
  users: 'Every account, and what each holds at every level',
  'access-groups': 'Groups of people, to give rights to many at once',
  'access-policies': 'The policies that decide who may do what, at every level',
  'access-features': 'The Nexus features an organization offers its workspaces',
  'access-core-services': 'How far an organization’s people go with each engine service',
  'access-modules': 'What an organization offers of each module',
  'access-service-accounts': 'The accounts modules and scripts act as',
  'access-approvals': 'What each module asks to do, approved before it runs',
  'access-simulator': 'Ask whether someone may do something, and why',
  'access-audit': 'Every change made to access: who, what, when',
  models: 'Who may chat with which model',
  'system-layers': 'The ABI code as layered planes',
  'system-diagrams': 'The ABI code as a diagram',
  drives: 'Where the platform stores files',
  tables: 'The raw tables of the Nexus database',
  ...Object.fromEntries(SYSTEM_VIEWS.map((view) => [`system-${view.id}`, view.description])),
  ...Object.fromEntries(Object.entries(SERVICE_DESCRIPTIONS).map(([service, text]) => [`service-${service}`, text])),
};

/** The caller's own pages, by link. */
export const ACCOUNT_PAGE_DESCRIPTIONS: Record<string, string> = {
  '/account/profile': 'Your name, photo and contact details',
  '/account/appearance': 'Light or dark theme',
  '/account/api-keys': 'Your keys to call the API',
  '/account/security': 'Password and sign-in',
  '/account/notifications': 'What you are told, and how',
};

/** The pickers atop the column: what each picks and what it drives (shown after a pause). */
export const SCOPE_PICKER_DESCRIPTIONS = {
  /** In a workspace's Settings. */
  workspaceOrganization: 'The organization of the workspace below. Another one opens its first workspace',
  workspace: 'The workspace every page below sets. Another one opens the same page there',
  /** In an organization's Settings. */
  organization: 'The organization every page below sets. Another one opens the same page there',
};
