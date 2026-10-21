/** Service views by API name; unknown services get a sensible generic view. */
import { Database } from 'lucide-react';
import type { ServiceView } from './types';
import { objectStorageView } from './object-storage';
import { secretView } from './secret';
import { keyValueView } from './keyvalue';
import { cacheView } from './cache';
import { documentView } from './document';
import { vectorStoreView } from './vector-store';
import { tripleStoreView } from './triple-store';
import { datasetView } from './dataset';
import { sourceControlView } from './source-control';
import { codingEnvironmentView } from './coding-environment';
import { modelRegistryView } from './model-registry';
import { emailView } from './email';
import { eventView } from './event';
import { activityLogView } from './activity-log';
import { busView } from './bus';
import { discoveryView } from './discovery';

const VIEWS: ServiceView[] = [
  objectStorageView,
  secretView,
  keyValueView,
  cacheView,
  documentView,
  vectorStoreView,
  tripleStoreView,
  datasetView,
  sourceControlView,
  codingEnvironmentView,
  modelRegistryView,
  emailView,
  eventView,
  activityLogView,
  busView,
  discoveryView,
];

const BY_NAME = new Map(VIEWS.map((v) => [v.name, v]));

export function registerServiceView(view: ServiceView): void {
  BY_NAME.set(view.name, view);
}

export function genericView(name: string): ServiceView {
  const label = name.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
  return {
    name,
    label,
    description: `Data held by the ${label.toLowerCase()} service.`,
    icon: Database,
    group: 'Platform',
    noun: { one: 'entry', many: 'entries' },
    editor: { language: () => 'plaintext' },
  };
}

export function viewFor(name: string): ServiceView {
  return BY_NAME.get(name) ?? genericView(name);
}
