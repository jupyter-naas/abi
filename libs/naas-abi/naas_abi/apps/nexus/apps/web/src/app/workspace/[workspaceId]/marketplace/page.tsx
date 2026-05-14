'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  Search, Bot, X, Cpu, Tag, CheckCircle2, AlertTriangle,
  FileText, Presentation, Table2, Trello, Calendar, ExternalLink,
  LayoutGrid, GitBranch, Network, Workflow, Download,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useTenant } from '@/contexts/tenant-context';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ModuleInfo {
  module_path: string;
  name: string;
  description: string;
  logo_url: string | null;
  category: string;
  installed: boolean;
  model: string | null;
  slug: string | null;
  agent_type: string | null;
  system_prompt_preview: string | null;
  functional: boolean;
}

interface ModulesResponse {
  installed: ModuleInfo[];
  available: ModuleInfo[];
}

type ArtifactType = 'all' | 'agents' | 'applications' | 'tools' | 'ontologies' | 'workflows' | 'pipelines';
type StatusFilter = 'all' | 'installed' | 'available' | 'coming-soon';

// ---------------------------------------------------------------------------
// Static metadata
// ---------------------------------------------------------------------------

const TYPE_LABELS: Record<ArtifactType, string> = {
  all: 'All',
  agents: 'Agents',
  applications: 'Applications',
  tools: 'Tools',
  ontologies: 'Ontologies',
  workflows: 'Workflows',
  pipelines: 'Pipelines',
};

const TYPE_ICONS: Record<ArtifactType, React.ReactNode> = {
  all: <LayoutGrid size={12} />,
  agents: <Bot size={12} />,
  applications: <ExternalLink size={12} />,
  tools: <FileText size={12} />,
  ontologies: <Network size={12} />,
  workflows: <Workflow size={12} />,
  pipelines: <GitBranch size={12} />,
};

const MODULE_CATEGORY_TO_TYPE: Record<string, ArtifactType> = {
  ai: 'agents',
  domain: 'agents',
  application: 'applications',
  core: 'agents',
};

const CATEGORY_LABELS: Record<string, string> = {
  core: 'Core',
  ai: 'AI',
  application: 'Application',
  domain: 'Domain',
};

const CATEGORY_COLORS: Record<string, string> = {
  core: 'bg-workspace-accent/10 text-workspace-accent',
  ai: 'bg-blue-500/10 text-blue-500',
  application: 'bg-purple-500/10 text-purple-500',
  domain: 'bg-amber-500/10 text-amber-600',
};

// ---------------------------------------------------------------------------
// Community vs Enterprise model (Red Hat model for AI infrastructure)
//
// Community  — MIT licensed, self-hosted, self-maintained. Free.
// Enterprise — Naas maintains, patches, and guarantees the agent.
//              A predictable maintenance fee, not a license.
//              Domain expert agents all fall here: Naas tunes the
//              system prompts, fixes API drift, and keeps ontologies current.
// ---------------------------------------------------------------------------

const ENTERPRISE_MAINTENANCE_FEE_USD = 19; // per agent per month (early-access rate)
const ENTERPRISE_CTA_URL = 'https://naas.ai/enterprise';

// Which module categories are Enterprise-maintained by Naas
const ENTERPRISE_CATEGORIES = new Set(['domain']);

// ---------------------------------------------------------------------------
// TCO / Pricing helpers
// ---------------------------------------------------------------------------

// Monthly estimates assume ~500 agent interactions at avg 2 000 tokens each.
// Input/output split 60/40. Prices in USD per 1M tokens (as of mid-2025).
const MODEL_PRICING: Record<string, { input: number; output: number; label: string }> = {
  'gpt-4o':           { input: 2.50,  output: 10.00, label: 'GPT-4o'         },
  'gpt-4o-mini':      { input: 0.15,  output: 0.60,  label: 'GPT-4o mini'    },
  'gpt-4':            { input: 30.00, output: 60.00, label: 'GPT-4'          },
  'gpt-3.5-turbo':    { input: 0.50,  output: 1.50,  label: 'GPT-3.5 Turbo'  },
  'o1':               { input: 15.00, output: 60.00, label: 'o1'             },
  'o3-mini':          { input: 1.10,  output: 4.40,  label: 'o3-mini'        },
  'claude-opus':      { input: 15.00, output: 75.00, label: 'Claude Opus'    },
  'claude-sonnet':    { input: 3.00,  output: 15.00, label: 'Claude Sonnet'  },
  'claude-haiku':     { input: 0.25,  output: 1.25,  label: 'Claude Haiku'   },
  'gemini-1.5-pro':   { input: 3.50,  output: 10.50, label: 'Gemini 1.5 Pro' },
  'gemini-1.5-flash': { input: 0.075, output: 0.30,  label: 'Gemini Flash'   },
};

const MONTHLY_INTERACTIONS = 500;
const AVG_TOKENS = 2_000;
const INPUT_RATIO = 0.6;

function estimateMonthlyUSD(modelKey: string): number | null {
  const entry = Object.entries(MODEL_PRICING).find(([k]) => modelKey.toLowerCase().includes(k));
  if (!entry) return null;
  const { input, output } = entry[1];
  const totalTokens = MONTHLY_INTERACTIONS * AVG_TOKENS;
  const inputTokens = totalTokens * INPUT_RATIO;
  const outputTokens = totalTokens * (1 - INPUT_RATIO);
  return (inputTokens * input + outputTokens * output) / 1_000_000;
}

function formatUSD(usd: number): string {
  if (usd < 1) return `~$${(usd * 100).toFixed(0)}¢/mo`;
  if (usd < 10) return `~$${usd.toFixed(1)}/mo`;
  return `~$${Math.round(usd)}/mo`;
}

function isEnterprise(mod: ModuleInfo): boolean {
  return ENTERPRISE_CATEGORIES.has(mod.category);
}

// Tier derivation — price badge is always informational regardless of functional status.
function getPriceLabel(mod: ModuleInfo): {
  price: string;
  tier: 'community' | 'enterprise' | 'early-access' | 'installed';
} {
  if (mod.installed) return { price: 'Installed', tier: 'installed' };
  if (isEnterprise(mod)) {
    const llm = mod.model ? estimateMonthlyUSD(mod.model) : null;
    const total = ENTERPRISE_MAINTENANCE_FEE_USD + (llm ?? 0);
    return { price: `~$${Math.round(total)}/mo`, tier: mod.functional ? 'enterprise' : 'early-access' };
  }
  return { price: 'Community', tier: 'community' };
}

const PRICE_STYLE: Record<string, string> = {
  installed:    'text-emerald-600 bg-emerald-500/10',
  enterprise:   'text-blue-600 bg-blue-500/10',
  'early-access': 'text-amber-600 bg-amber-500/10',
  community:    'text-muted-foreground bg-muted',
};

type Pricing = {
  label: string;
  labelStyle: string;
  cta: string;
  ctaStyle: string;
  ctaDisabled: boolean;
  ctaUrl?: string;
};

function getModulePricing(mod: ModuleInfo): Pricing {
  const { price, tier } = getPriceLabel(mod);
  if (tier === 'installed') {
    return { label: price, labelStyle: PRICE_STYLE.installed, cta: 'Installed', ctaStyle: 'bg-emerald-500/10 text-emerald-600 cursor-default', ctaDisabled: true };
  }
  if (tier === 'enterprise') {
    return { label: price, labelStyle: PRICE_STYLE.enterprise, cta: 'Subscribe', ctaStyle: 'bg-blue-600 text-white hover:bg-blue-700', ctaDisabled: false, ctaUrl: ENTERPRISE_CTA_URL };
  }
  if (tier === 'early-access') {
    return { label: price, labelStyle: PRICE_STYLE['early-access'], cta: 'Early access', ctaStyle: 'bg-amber-500 text-white hover:bg-amber-600', ctaDisabled: false, ctaUrl: ENTERPRISE_CTA_URL };
  }
  // community
  return { label: price, labelStyle: PRICE_STYLE.community, cta: 'Install', ctaStyle: 'bg-workspace-accent text-white hover:bg-workspace-accent/90', ctaDisabled: false };
}

function getStaticPricing(status: 'available' | 'coming-soon'): Pricing {
  if (status === 'available') {
    return { label: 'Community', labelStyle: PRICE_STYLE.community, cta: 'Open', ctaStyle: 'bg-workspace-accent text-white hover:bg-workspace-accent/90', ctaDisabled: false };
  }
  return { label: 'Coming soon', labelStyle: PRICE_STYLE.community, cta: 'Coming soon', ctaStyle: 'bg-muted text-muted-foreground cursor-not-allowed', ctaDisabled: true };
}

// Full TCO breakdown shown in the ID Card panel
function TcoBadge({ mod }: { mod: ModuleInfo }) {
  const llmEst = mod.model ? estimateMonthlyUSD(mod.model) : null;
  const ent = isEnterprise(mod);
  if (!llmEst && !ent) return null;

  const modelEntry = mod.model
    ? Object.entries(MODEL_PRICING).find(([k]) => mod.model!.toLowerCase().includes(k))
    : null;
  const modelLabel = modelEntry ? modelEntry[1].label : (mod.model ?? 'Unknown');
  const llm = llmEst ?? 0;
  const maintenance = ent ? ENTERPRISE_MAINTENANCE_FEE_USD : 0;

  return (
    <div className="border bg-muted/30 p-3 space-y-2.5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Estimated TCO</p>
        {ent && (
          <span className="px-2 py-0.5 text-xs font-medium bg-blue-500/10 text-blue-600">Enterprise</span>
        )}
        {!ent && (
          <span className="px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">Community</span>
        )}
      </div>
      <div className="space-y-1.5 text-xs text-muted-foreground">
        {mod.model && (
          <>
            <div className="flex justify-between">
              <span>Model</span>
              <span className="font-medium text-foreground">{modelLabel}</span>
            </div>
            <div className="flex justify-between">
              <span>Assumption</span>
              <span>{MONTHLY_INTERACTIONS} interactions/mo, ~{(AVG_TOKENS / 1000).toFixed(0)}k tokens each</span>
            </div>
            <div className="flex justify-between">
              <span>LLM cost</span>
              <span className="font-medium text-foreground">{formatUSD(llm)}</span>
            </div>
          </>
        )}
        {ent && (
          <div className="flex justify-between">
            <span>Maintenance fee</span>
            <span className="font-medium text-foreground">${maintenance}/mo</span>
          </div>
        )}
      </div>
      <div className="flex justify-between items-center border-t pt-2">
        <span className="text-xs font-semibold">Total monthly</span>
        <span className="text-sm font-bold text-blue-600">{formatUSD(llm + maintenance)}</span>
      </div>
      {ent && (
        <div className="border-t pt-2.5 space-y-1.5">
          <p className="text-xs font-semibold text-foreground">What the maintenance fee covers</p>
          <ul className="space-y-1 text-xs text-muted-foreground">
            <li className="flex items-start gap-1.5">
              <span className="mt-0.5 text-blue-500 shrink-0">+</span>
              <span>Agent kept current when the underlying model is deprecated or repriced</span>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="mt-0.5 text-blue-500 shrink-0">+</span>
              <span>System prompt tuned when regulations, workflows, or standards change</span>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="mt-0.5 text-blue-500 shrink-0">+</span>
              <span>Tool and API integrations patched when third-party services drift</span>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="mt-0.5 text-blue-500 shrink-0">+</span>
              <span>Ontology connections updated as the knowledge graph evolves</span>
            </li>
          </ul>
          <p className="text-xs text-muted-foreground/60 pt-0.5">
            Not a license. The agent is MIT licensed and yours to fork. You pay for the people keeping it production-ready.
          </p>
        </div>
      )}
      {!ent && (
        <p className="text-xs text-muted-foreground/60 border-t pt-2">
          Community tier. MIT licensed, self-hosted, self-maintained.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Static artifacts
// ---------------------------------------------------------------------------

interface StaticArtifact {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  type: ArtifactType;
  status: 'available' | 'coming-soon';
  url?: string;
}

const STATIC_ARTIFACTS: StaticArtifact[] = [
  { id: 'docs', name: 'Docs', description: 'Rich text editor for documentation, notes, and runbooks with agent assistance.', icon: <FileText size={22} />, type: 'tools', status: 'coming-soon' },
  { id: 'slides', name: 'Slides', description: 'Build and narrate presentations driven by your knowledge graph.', icon: <Presentation size={22} />, type: 'tools', status: 'coming-soon' },
  { id: 'sheets', name: 'Sheets', description: 'Intelligent spreadsheets with formula support and live data connectors.', icon: <Table2 size={22} />, type: 'tools', status: 'coming-soon' },
  { id: 'board', name: 'Board', description: 'Kanban boards and whiteboards to manage tasks and visual workflows.', icon: <Trello size={22} />, type: 'tools', status: 'coming-soon' },
  { id: 'calendar', name: 'Calendar', description: 'Schedule and timeline management synced with your agents.', icon: <Calendar size={22} />, type: 'tools', status: 'coming-soon' },
  { id: 'ontologies-community', name: 'Community Ontologies', description: 'Browse and install shared ontology modules contributed by the ABI community.', icon: <Network size={22} />, type: 'ontologies', status: 'coming-soon' },
  { id: 'workflows-templates', name: 'Workflow Templates', description: 'Reusable multi-step agent workflows for common business and data processes.', icon: <Workflow size={22} />, type: 'workflows', status: 'coming-soon' },
  { id: 'pipelines-blueprints', name: 'Pipeline Blueprints', description: 'Pre-built data ingestion and transformation pipelines ready to configure.', icon: <GitBranch size={22} />, type: 'pipelines', status: 'coming-soon' },
];

// ---------------------------------------------------------------------------
// Module avatar
// ---------------------------------------------------------------------------

function ModuleAvatar({ mod, className, imgClassName }: { mod: ModuleInfo; className?: string; imgClassName?: string }) {
  const [imgFailed, setImgFailed] = useState(false);
  const isPortrait = mod.category === 'domain';
  return (
    <div className={cn('relative overflow-hidden bg-muted', className)}>
      {mod.logo_url && !imgFailed ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={mod.logo_url}
          alt={mod.name}
          className={cn(isPortrait ? 'h-full w-full object-cover object-top' : 'max-h-full max-w-full object-contain', imgClassName)}
          onError={() => setImgFailed(true)}
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center">
          <Bot size={36} className="text-muted-foreground/30" />
        </div>
      )}
      {isPortrait && mod.logo_url && !imgFailed && (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-black/20 to-transparent" />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module card
// ---------------------------------------------------------------------------

function ModuleCard({ mod, onClick }: { mod: ModuleInfo; onClick: () => void }) {
  const isPortrait = mod.category === 'domain';
  const pricing = getModulePricing(mod);

  return (
    // Whole card is clickable; CTA button stops propagation to avoid double-firing
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      className="glass-card flex flex-col overflow-hidden cursor-pointer transition-all hover:border-primary/30 hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
    >
      <ModuleAvatar
        mod={mod}
        className={cn('w-full', isPortrait ? 'h-44' : 'flex h-32 items-center justify-center p-6')}
      />

      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="line-clamp-1 font-semibold leading-tight">{mod.name}</h3>
        <span className={cn('self-start px-2 py-0.5 text-xs font-medium', CATEGORY_COLORS[mod.category] ?? 'bg-muted text-muted-foreground')}>
          {CATEGORY_LABELS[mod.category] ?? mod.category}
        </span>
        <p className="line-clamp-2 flex-1 text-xs text-muted-foreground">
          {mod.description || mod.module_path}
        </p>

        {/* Pricing + CTA — CTA stops propagation so it doesn't re-open the panel */}
        <div className="flex items-center justify-between gap-2 pt-1 border-t border-border/50 mt-1">
          <span className={cn('px-2 py-0.5 text-xs font-medium tabular-nums', pricing.labelStyle)}>
            {pricing.label}
          </span>
          {pricing.ctaUrl && !pricing.ctaDisabled ? (
            <a
              href={pricing.ctaUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className={cn(
                'flex items-center gap-1 px-3 py-1 text-xs font-semibold transition-colors',
                pricing.ctaStyle,
              )}
            >
              <ExternalLink size={11} />
              {pricing.cta}
            </a>
          ) : (
            <button
              disabled={pricing.ctaDisabled}
              onClick={(e) => e.stopPropagation()}
              className={cn(
                'flex items-center gap-1 px-3 py-1 text-xs font-semibold transition-colors',
                pricing.ctaStyle,
              )}
            >
              {!pricing.ctaDisabled && <Download size={11} />}
              {pricing.cta}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Static artifact card
// ---------------------------------------------------------------------------

function StaticCard({ artifact }: { artifact: StaticArtifact }) {
  const pricing = getStaticPricing(artifact.status);

  const inner = (
    <div className={cn('glass-card flex flex-col gap-3 p-5 transition-all h-full', artifact.status === 'available' ? 'hover:border-workspace-accent hover:shadow-md' : 'opacity-60')}>
      <div className="flex h-11 w-11 items-center justify-center bg-workspace-accent/10 text-workspace-accent">
        {artifact.icon}
      </div>
      <div className="flex-1">
        <h3 className="font-semibold leading-tight">{artifact.name}</h3>
        <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{artifact.description}</p>
      </div>
      {/* Pricing + CTA */}
      <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/50">
        <span className={cn('px-2 py-0.5 text-xs font-medium', pricing.labelStyle)}>
          {pricing.label}
        </span>
        <button
          disabled={pricing.ctaDisabled}
          className={cn('flex items-center gap-1 px-3 py-1 text-xs font-semibold transition-colors', pricing.ctaStyle)}
        >
          {artifact.status === 'available' && <ExternalLink size={11} />}
          {pricing.cta}
        </button>
      </div>
    </div>
  );

  if (artifact.status === 'available' && artifact.url) {
    return <a href={artifact.url} target="_blank" rel="noreferrer noopener" className="h-full block">{inner}</a>;
  }
  return inner;
}

// ---------------------------------------------------------------------------
// External app card (from tenant config)
// ---------------------------------------------------------------------------

function ExternalAppCard({ app }: { app: { name: string; url: string; description?: string | null; icon_emoji?: string | null } }) {
  return (
    <a href={app.url} target="_blank" rel="noreferrer noopener">
      <div className="glass-card flex flex-col gap-3 p-5 transition-all hover:border-workspace-accent hover:shadow-md">
        <div className="flex h-11 w-11 items-center justify-center bg-workspace-accent/10 text-2xl">
          {app.icon_emoji ?? <ExternalLink size={22} className="text-workspace-accent" />}
        </div>
        <div className="flex-1">
          <h3 className="font-semibold leading-tight">{app.name}</h3>
          {app.description && <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{app.description}</p>}
        </div>
        <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/50">
          <span className="px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">Free</span>
          <button className="flex items-center gap-1 px-3 py-1 text-xs font-semibold bg-workspace-accent text-white hover:bg-workspace-accent/90 transition-colors">
            <ExternalLink size={11} /> Open
          </button>
        </div>
      </div>
    </a>
  );
}

// ---------------------------------------------------------------------------
// Agent ID Card panel
// ---------------------------------------------------------------------------

function AgentIdCard({ mod, onClose }: { mod: ModuleInfo; onClose: () => void }) {
  const isPortrait = mod.category === 'domain';
  const pricing = getModulePricing(mod);

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-background shadow-2xl border-l">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Agent ID Card</span>
          <button onClick={onClose} className="p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <ModuleAvatar
            mod={mod}
            className={cn('w-full', isPortrait ? 'h-64' : 'flex h-44 items-center justify-center p-10')}
          />

          <div className="space-y-4 p-5">
            {/* Name + status */}
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold">{mod.name}</h2>
                {mod.slug && <p className="mt-0.5 font-mono text-xs text-muted-foreground">{mod.slug}</p>}
              </div>
              <div className="flex flex-col items-end gap-1.5">
                {mod.installed && (
                  <span className="flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-600">
                    <CheckCircle2 size={11} /> Installed
                  </span>
                )}
                {!mod.functional && (
                  <span className="flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-600">
                    <AlertTriangle size={11} /> Not functional yet
                  </span>
                )}
              </div>
            </div>

            {/* Badges */}
            <div className="flex flex-wrap gap-2">
              <span className={cn('px-2.5 py-0.5 text-xs font-medium', CATEGORY_COLORS[mod.category] ?? 'bg-muted text-muted-foreground')}>
                <Tag size={10} className="mr-1 inline" />
                {CATEGORY_LABELS[mod.category] ?? mod.category}
              </span>
              {mod.agent_type && (
                <span className="bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">{mod.agent_type}</span>
              )}
              {mod.model && (
                <span className="flex items-center gap-1 bg-blue-500/10 px-2.5 py-0.5 text-xs font-medium text-blue-600">
                  <Cpu size={10} /> {mod.model}
                </span>
              )}
            </div>

            {/* Description */}
            {mod.description && (
              <p className="text-sm leading-relaxed text-muted-foreground">{mod.description}</p>
            )}

            {/* System prompt */}
            {mod.system_prompt_preview && (
              <div className="border bg-muted/40 p-3">
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">System prompt</p>
                <p className="text-xs leading-relaxed text-foreground/80">{mod.system_prompt_preview}</p>
              </div>
            )}

            {/* TCO estimate */}
            <TcoBadge mod={mod} />

            {/* Module path */}
            <div className="border bg-muted/30 p-3 space-y-1.5">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Module</p>
              <p className="break-all font-mono text-xs text-muted-foreground">{mod.module_path}</p>
            </div>

            {/* CTA */}
            {pricing.ctaUrl && !pricing.ctaDisabled ? (
              <a
                href={pricing.ctaUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={cn('w-full py-2.5 text-sm font-semibold transition-colors flex items-center justify-center gap-2', pricing.ctaStyle)}
              >
                <ExternalLink size={14} />
                {pricing.cta}
              </a>
            ) : (
              <button
                disabled={pricing.ctaDisabled}
                className={cn('w-full py-2.5 text-sm font-semibold transition-colors flex items-center justify-center gap-2', pricing.ctaStyle)}
              >
                {!pricing.ctaDisabled && <Download size={14} />}
                {pricing.cta}
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const ALL_TYPES: ArtifactType[] = ['all', 'agents', 'applications', 'tools', 'ontologies', 'workflows', 'pipelines'];

export default function MarketplacePage() {
  const searchParams = useSearchParams();
  const tenant = useTenant();

  const [typeFilter, setTypeFilter] = useState<ArtifactType>(() => {
    const t = searchParams?.get('type') as ArtifactType | null;
    return t && ALL_TYPES.includes(t) ? t : 'all';
  });
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');
  const [data, setData] = useState<ModulesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMod, setSelectedMod] = useState<ModuleInfo | null>(null);

  useEffect(() => {
    const t = searchParams?.get('type') as ArtifactType | null;
    if (t && ALL_TYPES.includes(t)) setTypeFilter(t);
  }, [searchParams]);

  useEffect(() => {
    setLoading(true);
    authFetch(`${getApiUrl()}/api/modules/`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((d: ModulesResponse) => setData(d))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const allModules = useMemo<ModuleInfo[]>(() => {
    if (!data) return [];
    const map = new Map<string, ModuleInfo>();
    for (const m of data.available) map.set(m.module_path, m);
    for (const m of data.installed) map.set(m.module_path, { ...map.get(m.module_path) ?? m, installed: true });
    return Array.from(map.values());
  }, [data]);

  const tenantArtifacts = useMemo<StaticArtifact[]>(() =>
    tenant.apps.map((app) => ({
      id: `external-${app.url}`,
      name: app.name,
      description: app.description ?? '',
      icon: app.icon_emoji ? <span className="text-2xl">{app.icon_emoji}</span> : <ExternalLink size={22} />,
      type: 'tools' as ArtifactType,
      status: 'available' as const,
      url: app.url,
    })),
  [tenant.apps]);

  const allStatic = useMemo(() => [...tenantArtifacts, ...STATIC_ARTIFACTS], [tenantArtifacts]);

  const typeCounts = useMemo(() => {
    const counts: Partial<Record<ArtifactType, number>> = {};
    for (const m of allModules) {
      const t = MODULE_CATEGORY_TO_TYPE[m.category] ?? 'agents';
      counts[t] = (counts[t] ?? 0) + 1;
    }
    for (const s of allStatic) {
      counts[s.type] = (counts[s.type] ?? 0) + 1;
    }
    counts.all = allModules.length + allStatic.length;
    return counts;
  }, [allModules, allStatic]);

  const filteredModules = useMemo(() => allModules.filter((m) => {
    const t = MODULE_CATEGORY_TO_TYPE[m.category] ?? 'agents';
    if (typeFilter !== 'all' && t !== typeFilter) return false;
    if (statusFilter === 'installed' && !m.installed) return false;
    if (statusFilter === 'available' && m.installed) return false;
    if (statusFilter === 'coming-soon') return false;
    if (search) {
      const q = search.toLowerCase();
      if (!m.name.toLowerCase().includes(q) && !m.description.toLowerCase().includes(q)) return false;
    }
    return true;
  }), [allModules, typeFilter, statusFilter, search]);

  const filteredStatic = useMemo(() => allStatic.filter((s) => {
    if (typeFilter !== 'all' && s.type !== typeFilter) return false;
    if (statusFilter === 'installed') return false;
    if (statusFilter === 'available' && s.status !== 'available') return false;
    if (statusFilter === 'coming-soon' && s.status !== 'coming-soon') return false;
    if (search) {
      const q = search.toLowerCase();
      if (!s.name.toLowerCase().includes(q) && !s.description.toLowerCase().includes(q)) return false;
    }
    return true;
  }), [allStatic, typeFilter, statusFilter, search]);

  const groupedModules = useMemo(() => {
    if (typeFilter !== 'all') return { '': filteredModules };
    return filteredModules.reduce<Record<string, ModuleInfo[]>>((acc, m) => {
      const key = CATEGORY_LABELS[m.category] ?? m.category;
      (acc[key] ??= []).push(m);
      return acc;
    }, {});
  }, [filteredModules, typeFilter]);

  const groupedStatic = useMemo(() => {
    if (typeFilter !== 'all') return { '': filteredStatic };
    return filteredStatic.reduce<Record<string, StaticArtifact[]>>((acc, s) => {
      const key = TYPE_LABELS[s.type];
      (acc[key] ??= []).push(s);
      return acc;
    }, {});
  }, [filteredStatic, typeFilter]);

  const totalResults = filteredModules.length + filteredStatic.length;

  return (
    <div className="flex h-full flex-col">
      <Header title="Marketplace" subtitle="Agents, applications, tools, ontologies, workflows and pipelines" />

      <div className="flex-1 overflow-auto">
        <div className="p-6 space-y-5">

          {/* Search */}
          <div className="relative max-w-2xl">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search the marketplace…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-10 w-full border bg-background pl-10 pr-4 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Type pills */}
            {ALL_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={cn(
                  'flex items-center gap-1.5 border px-3 py-1.5 text-xs font-medium transition-colors',
                  typeFilter === t
                    ? 'border-workspace-accent bg-workspace-accent text-white'
                    : 'border-transparent bg-muted text-muted-foreground hover:text-foreground',
                )}
              >
                {TYPE_ICONS[t]}
                {TYPE_LABELS[t]}
                {typeCounts[t] !== undefined && (
                  <span className={cn('px-1.5 py-0.5 text-xs tabular-nums', typeFilter === t ? 'bg-white/20' : 'bg-background')}>
                    {typeCounts[t]}
                  </span>
                )}
              </button>
            ))}

            <div className="mx-1 h-5 w-px bg-border" />

            {/* Status pills */}
            {(['all', 'installed', 'available', 'coming-soon'] as StatusFilter[]).map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={cn(
                  'border px-3 py-1.5 text-xs font-medium transition-colors',
                  statusFilter === s
                    ? 'border-foreground bg-foreground text-background'
                    : 'border-transparent bg-muted text-muted-foreground hover:text-foreground',
                )}
              >
                {s === 'all' ? 'All status' : s === 'coming-soon' ? 'Coming soon' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>

          {/* States */}
          {loading && (
            <div className="flex items-center justify-center py-20 text-muted-foreground">
              <LayoutGrid size={20} className="mr-2 animate-pulse" /> Loading marketplace…
            </div>
          )}
          {error && (
            <div className="border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
              Failed to load: {error}
            </div>
          )}
          {!loading && !error && totalResults === 0 && (
            <p className="py-12 text-center text-sm text-muted-foreground">Nothing matches your search.</p>
          )}

          {/* Grid */}
          {!loading && !error && totalResults > 0 && (
            <div className="space-y-10">
              {Object.entries(groupedModules)
                .filter(([, mods]) => mods.length > 0)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([label, mods]) => (
                  <section key={label || 'modules'}>
                    {label && (
                      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">{label}</h2>
                    )}
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      {mods.map((mod) => (
                        <ModuleCard key={mod.module_path} mod={mod} onClick={() => setSelectedMod(mod)} />
                      ))}
                    </div>
                  </section>
                ))}

              {Object.entries(groupedStatic)
                .filter(([, items]) => items.length > 0)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([label, items]) => (
                  <section key={label || 'static'}>
                    {label && (
                      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">{label}</h2>
                    )}
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      {items.map((artifact) =>
                        artifact.id.startsWith('external-') ? (
                          <ExternalAppCard
                            key={artifact.id}
                            app={{ name: artifact.name, url: artifact.url ?? '#', description: artifact.description }}
                          />
                        ) : (
                          <StaticCard key={artifact.id} artifact={artifact} />
                        ),
                      )}
                    </div>
                  </section>
                ))}
            </div>
          )}
        </div>
      </div>

      {selectedMod && (
        <AgentIdCard mod={selectedMod} onClose={() => setSelectedMod(null)} />
      )}
    </div>
  );
}
