import type { OntologyTopicIconName } from './ontology-topic-glyphs';
import type { DictionaryTerm } from './ontology-dictionary-tree';

export type OntologyTopicSubject = {
  name: string;
  id?: string;
  path?: string;
  moduleName?: string;
  type?: DictionaryTerm['type'];
  parents?: Array<{ name: string }>;
  sources?: Array<{ name: string; path: string; moduleName: string }>;
};

/** Presentation hints only: these rules never change ontology types or declarations. */
const TOPICS: Array<[RegExp, OntologyTopicIconName]> = [
  [/\b(security|cyber|screening|clearance|access provisioning|access control|permission|permissions|authentication|authorization)\b/, 'security'],
  [/\b(safety|hazard|hazards|recall|health|medical)\b/, 'health-and-safety-outline'],
  [/\b(currency|currencies|payment|payments|expense|expenses|invoice|invoices|payroll)\b/, 'payments-outline'],
  [/\b(finance|financial|budget|budgets|accounting|treasury|bank|tax)\b/, 'account-balance-outline'],
  [/\b(geospatial|geographic|geography|spatial|country|countries|global|world)\b/, 'public'],
  [/\b(time|temporal|interval|instant|duration|cadence|deadline)\b/, 'schedule-outline'],
  [/\b(location|locations|site|sites|place|places|address|region)\b/, 'location-on-outline'],
  [/\b(facility|facilities|building|buildings|estate|premises)\b/, 'apartment'],
  [/\b(calendar|scheduling|schedule|attendance|leave|event|events)\b/, 'event-note-outline'],
  [/\b(onboarding|offboarding|joiner|recruitment|employee|employees|badge)\b/, 'badge-outline'],
  [/\b(personnel|people|human resources|hr|workforce|team|teams|group|groups)\b/, 'groups-outline'],
  [/\b(ai|artificial intelligence|brain|abi|nexus|chatbot)\b/, 'smart-toy-outline'],
  [/\b(person|persons|user|users|participant|participants|officer|agent|agents)\b/, 'person-outline'],
  [/\b(intelligence|reasoning|cognition|cognitive|signal synthesis)\b/, 'psychology-outline'],
  [/\b(organization|organisation|company|companies|authority|authorities|business)\b/, 'corporate-fare'],
  [/\b(logistics|fleet|dispatch|shipping|transport|vehicle|vehicles|delivery)\b/, 'local-shipping-outline'],
  [/\b(stock|inventory|asset|assets|artifact|artifacts|product|products|procurement|supplier|vendor)\b/, 'inventory-2-outline'],
  [/\b(audit|compliance|policy|policies|governance|regulation|regulations|contract|contracts)\b/, 'policy-outline'],
  [/\b(maintenance|repair|repairs|work order|incident|incidents|operations)\b/, 'construction'],
  [/\b(training|education|learning|school|assessment|capability development)\b/, 'school-outline'],
  [/\b(science|scientific|laboratory|lab|research|experiment)\b/, 'science-outline'],
  [/\b(quality|validation|validated|verification|approval|approvals|status)\b/, 'verified-outline'],
  [/\b(partner|partners|partnership|stakeholder|stakeholders|engagement|coordination)\b/, 'handshake-outline'],
  [/\b(communication|communications|conversation|conversations|chat|message|messages|briefing)\b/, 'forum-outline'],
  [/\b(alert|alerts|alerting|notification|notifications|watch)\b/, 'notifications-outline'],
  [/\b(analytics|forecast|forecasting|prediction|statistics|risk|indicator|indicators)\b/, 'query-stats'],
  [/\b(monitoring|measurement|measurements|metric|metrics|score|performance)\b/, 'monitoring'],
  [/\b(unit|units|measure|scale|length|distance|dimension|dimensions)\b/, 'straighten'],
  [/\b(database|dataset|datasets|data source|triple store|vector store)\b/, 'database-outline'],
  [/\b(document|documents|record|records|evidence|information|report|reports|notice)\b/, 'description-outline'],
  [/\b(network|infrastructure|server|servers|router|host|hosts)\b/, 'router-outline'],
  [/\b(cloud|hosting)\b/, 'cloud-outline'],
  [/\b(code|coding|software|development|developer|sparql|query|queries|api|tool|tools)\b/, 'terminal'],
  [/\b(objective|objectives|goal|goals|plan|plans|planning|programme|program|roadmap|strategy|purpose)\b/, 'flag-outline'],
  [/\b(relation|relations|relationship|relationships|link|links)\b/, 'link'],
  [/\b(setting|settings|configuration|configure|provisioning)\b/, 'settings-outline'],
  [/\b(search|discovery)\b/, 'manage-search'],
  [/\b(task|tasks|assignment|assignments)\b/, 'assignment-outline'],
  [/\b(checklist|check|checks)\b/, 'checklist'],
  [/\b(file|files|folder|folders)\b/, 'folder-open-outline'],
  [/\b(process|processes|workflow|workflows|pipeline|pipelines|ledger|system|systems)\b/, 'account-tree-outline'],
];

function normalize(value: string) {
  return value.replace(/([A-Z])([A-Z][a-z])/g, '$1 $2').replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ');
}
// Every row of the ontology column, dictionary and graph explorer resolves its
// icon on each render, and names, parents and module names repeat heavily.
// Running ~45 regexes per lookup made opening the Ontology section block the
// dock click for hundreds of ms, so memoize the pure string -> icon mapping.
const MATCH_CACHE_LIMIT = 5000;
const matchCache = new Map<string, OntologyTopicIconName | null>();

function match(value: string): OntologyTopicIconName | undefined {
  const cached = matchCache.get(value);
  if (cached !== undefined) return cached ?? undefined;
  const text = normalize(value);
  const icon = TOPICS.find(([pattern]) => pattern.test(text))?.[1] ?? null;
  if (matchCache.size >= MATCH_CACHE_LIMIT) matchCache.clear();
  matchCache.set(value, icon);
  return icon ?? undefined;
}

/** Resolve the visible label first, then local context; never classify from an absolute path. */
export function ontologyTopicIcon(subject: OntologyTopicSubject): OntologyTopicIconName {
  const direct = match(subject.name);
  if (direct) return direct;
  if (subject.type === 'relationship') return 'link';
  if (subject.type === 'attribute') return 'checklist';
  if (subject.type === 'annotation') return 'description-outline';
  const localName = (subject.path || subject.id || '').split(/[/#]/).pop() || '';
  const named = match(localName);
  if (named) return named;
  for (const parent of subject.parents || []) {
    const inherited = match(parent.name);
    if (inherited) return inherited;
  }
  // Shared terms must not change icon if the API returns their source files in another order.
  for (const source of [...(subject.sources || [])].sort((a, b) => a.path.localeCompare(b.path))) {
    const sourceTopic = match(source.name) || match(source.path.split('/').pop() || '');
    if (sourceTopic) return sourceTopic;
  }
  return match(subject.moduleName || '') || (subject.type === 'individual' ? 'person-outline' : 'schema-outline');
}
