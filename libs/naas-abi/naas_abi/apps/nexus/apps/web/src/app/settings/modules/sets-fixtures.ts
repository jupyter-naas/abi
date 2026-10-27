/** Fixtures for the modules × workspaces tests. */
import type { ModuleScopeItem, ModuleScopesEntry, OrganizationSetView, SetsView } from '@/lib/iam-admin/types';
import type { SetCatalog } from './sets-model';

function item(type: string, module: string, name: string): ModuleScopeItem {
  return {
    name,
    display_name: name,
    description: '',
    icon: null,
    resource: `\${scope}:module:${type}/${module}/${name}`,
    actions: [],
  };
}

export const people: ModuleScopesEntry = {
  module: 'acme.people',
  agents: [item('agent', 'acme.people', 'Recruiter'), item('agent', 'acme.people', 'Coach')],
  apps: [item('app', 'acme.people', 'Directory')],
  workflows: [],
  pipelines: [],
  declared: {
    service: 'acme_people',
    version: 1,
    resource_types: [],
    actions: [
      { action: 'acme_people:ExportReport', level: 'write', resource_types: ['report'], description: '' },
    ],
  },
};

export const crm: ModuleScopesEntry = {
  module: 'acme.crm',
  agents: [item('agent', 'acme.crm', 'Sales')],
  apps: [],
  workflows: [item('workflow', 'acme.crm', 'Sync')],
  pipelines: [],
  declared: null,
};

export const catalog: SetCatalog = { modules: [people, crm], features: ['chat', 'files', 'apps'] };

export const organization: OrganizationSetView = {
  id: 'org-1',
  name: 'EDF',
  set: { modules: ['acme.people'], features: null },
  effective: { modules: ['acme.people'], features: null },
  editable: false,
  workspaces: [
    {
      id: 'ws-1',
      name: 'Research',
      set: { modules: ['acme.people', 'acme.crm'], features: ['chat'] },
      effective: { modules: ['acme.people'], features: ['chat'] },
      editable: true,
    },
    {
      id: 'ws-2',
      name: 'Ops',
      set: { modules: null, features: null },
      effective: { modules: ['acme.people'], features: null },
      editable: false,
    },
  ],
};

export const setsView: SetsView = {
  modules: catalog.modules,
  features: catalog.features,
  organizations: [organization],
};
