'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  Search, Bot, X, Cpu, Tag, CheckCircle2, AlertTriangle,
  FileText, Presentation, Table2, Trello, Calendar, ExternalLink,
  LayoutGrid, GitBranch, Network, Workflow, Download, AppWindow,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useTenant } from '@/contexts/tenant-context';
import Link from 'next/link';
import { useWorkspaceStore } from '@/stores/workspace';

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
  tier: string | null;
  maintainer: string | null;
  stripe_url: string | null;
  app_url: string | null;
}

interface ModulesResponse {
  installed: ModuleInfo[];
  available: ModuleInfo[];
}

// Marketplace config shapes (mirrors backend Pydantic models)
interface ModelPricingEntry {
  input_per_million: number;
  output_per_million: number;
  label: string;
}

interface MarketplaceUsageTier {
  label: string;
  interactions: number;
  avg_tokens: number;
  description: string;
}

interface MarketplacePricingConfig {
  maintenance_standard_usd: number;
  maintenance_early_access_usd: number;
  cta_url: string;
  enterprise_categories: string[];
  input_output_ratio: number;
}

interface MarketplaceConfig {
  pricing: MarketplacePricingConfig;
  usage_tiers: MarketplaceUsageTier[];
  model_pricing: Record<string, ModelPricingEntry>;
}

// Sensible defaults used while the config fetch is in-flight
const DEFAULT_MARKETPLACE_CONFIG: MarketplaceConfig = {
  pricing: {
    maintenance_standard_usd: 499,
    maintenance_early_access_usd: 299,
    cta_url: 'https://naas.ai/enterprise',
    enterprise_categories: ['domain'],
    input_output_ratio: 0.6,
  },
  usage_tiers: [
    { label: 'Starter',      interactions: 50,    avg_tokens: 2_000,  description: '~2 queries/day' },
    { label: 'Professional', interactions: 300,   avg_tokens: 5_000,  description: '~10 queries/day' },
    { label: 'Scale',        interactions: 2_000, avg_tokens: 10_000, description: '~65 queries/day, team use' },
  ],
  model_pricing: {
    'gpt-4o':           { input_per_million: 2.50,  output_per_million: 10.00, label: 'GPT-4o' },
    'gpt-4o-mini':      { input_per_million: 0.15,  output_per_million: 0.60,  label: 'GPT-4o mini' },
    'gpt-4':            { input_per_million: 30.00, output_per_million: 60.00, label: 'GPT-4' },
    'gpt-3.5-turbo':    { input_per_million: 0.50,  output_per_million: 1.50,  label: 'GPT-3.5 Turbo' },
    'o1':               { input_per_million: 15.00, output_per_million: 60.00, label: 'o1' },
    'o3-mini':          { input_per_million: 1.10,  output_per_million: 4.40,  label: 'o3-mini' },
    'claude-opus':      { input_per_million: 15.00, output_per_million: 75.00, label: 'Claude Opus' },
    'claude-sonnet':    { input_per_million: 3.00,  output_per_million: 15.00, label: 'Claude Sonnet' },
    'claude-haiku':     { input_per_million: 0.25,  output_per_million: 1.25,  label: 'Claude Haiku' },
    'gemini-1.5-pro':   { input_per_million: 3.50,  output_per_million: 10.50, label: 'Gemini 1.5 Pro' },
    'gemini-1.5-flash': { input_per_million: 0.075, output_per_million: 0.30,  label: 'Gemini Flash' },
  },
};

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
  alpha: 'applications',
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
// Pricing helpers — all driven by MarketplaceConfig from the API.
// No hardcoded fees, tiers, or model prices here.
// ---------------------------------------------------------------------------

function formatUSD(usd: number): string {
  if (usd < 0.01) return '<$0.01/mo';
  if (usd < 1)    return `~$${usd.toFixed(2)}/mo`;
  if (usd < 10)   return `~$${usd.toFixed(1)}/mo`;
  return `~$${Math.round(usd)}/mo`;
}

function isEnterprise(mod: ModuleInfo, cfg: MarketplaceConfig): boolean {
  // Per-agent TIER field from the source file takes priority
  if (mod.tier) return mod.tier === 'enterprise';
  return cfg.pricing.enterprise_categories.includes(mod.category);
}

function llmCostForTier(
  modelKey: string,
  interactions: number,
  avgTokens: number,
  cfg: MarketplaceConfig,
): number | null {
  const entry = Object.entries(cfg.model_pricing).find(([k]) => modelKey.toLowerCase().includes(k));
  if (!entry) return null;
  const { input_per_million, output_per_million } = entry[1];
  const total = interactions * avgTokens;
  const r = cfg.pricing.input_output_ratio;
  return (total * r * input_per_million + total * (1 - r) * output_per_million) / 1_000_000;
}

const PRICE_STYLE: Record<string, string> = {
  installed:      'text-emerald-600 bg-emerald-500/10',
  enterprise:     'text-blue-600 bg-blue-500/10',
  'early-access': 'text-amber-600 bg-amber-500/10',
  community:      'text-muted-foreground bg-muted',
};

type Pricing = {
  label: string;
  labelStyle: string;
  cta: string;
  ctaStyle: string;
  ctaDisabled: boolean;
  ctaUrl?: string;
};

function getModulePricing(mod: ModuleInfo, cfg: MarketplaceConfig): Pricing {
  if (mod.installed) {
    return { label: 'Installed', labelStyle: PRICE_STYLE.installed, cta: 'Installed', ctaStyle: 'bg-emerald-500/10 text-emerald-600 cursor-default', ctaDisabled: true };
  }
  if (isEnterprise(mod, cfg)) {
    const fee = mod.functional
      ? cfg.pricing.maintenance_standard_usd
      : cfg.pricing.maintenance_early_access_usd;
    const ctaUrl = mod.stripe_url ?? cfg.pricing.cta_url;
    if (mod.functional) {
      return { label: `$${fee}/mo`, labelStyle: PRICE_STYLE.enterprise, cta: 'Subscribe', ctaStyle: 'bg-blue-600 text-white hover:bg-blue-700', ctaDisabled: false, ctaUrl };
    }
    return { label: `$${fee}/mo`, labelStyle: PRICE_STYLE['early-access'], cta: 'Early access', ctaStyle: 'bg-amber-500 text-white hover:bg-amber-600', ctaDisabled: false, ctaUrl };
  }
  return { label: 'Community', labelStyle: PRICE_STYLE.community, cta: 'Install', ctaStyle: 'bg-workspace-accent text-white hover:bg-workspace-accent/90', ctaDisabled: false };
}

function getStaticPricing(status: 'available' | 'coming-soon'): Pricing {
  if (status === 'available') {
    return { label: 'Community', labelStyle: PRICE_STYLE.community, cta: 'Open', ctaStyle: 'bg-workspace-accent text-white hover:bg-workspace-accent/90', ctaDisabled: false };
  }
  return { label: 'Coming soon', labelStyle: PRICE_STYLE.community, cta: 'Coming soon', ctaStyle: 'bg-muted text-muted-foreground cursor-not-allowed', ctaDisabled: true };
}


// Full TCO breakdown shown in the ID Card panel.
// Separates maintenance fee (fixed, to Naas) from LLM token costs (variable, to model provider).
function TcoBadge({ mod, cfg }: { mod: ModuleInfo; cfg: MarketplaceConfig }) {
  const ent = isEnterprise(mod, cfg);
  const hasModel = !!mod.model;
  if (!ent && !hasModel) return null;

  const modelEntry = mod.model
    ? Object.entries(cfg.model_pricing).find(([k]) => mod.model!.toLowerCase().includes(k))
    : null;
  const modelLabel = modelEntry ? modelEntry[1].label : (mod.model ?? 'Unknown');
  const maintenance = ent
    ? (mod.functional ? cfg.pricing.maintenance_standard_usd : cfg.pricing.maintenance_early_access_usd)
    : 0;

  return (
    <div className="border bg-muted/30 p-3 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Cost breakdown</p>
        <span className={cn('px-2 py-0.5 text-xs font-medium', ent ? 'bg-blue-500/10 text-blue-600' : 'bg-muted text-muted-foreground')}>
          {ent ? 'Enterprise' : 'Community'}
        </span>
      </div>

      {/* Row 1: Maintenance fee — fixed, paid to Naas */}
      {ent && (
        <div className="space-y-1">
          <div className="flex justify-between items-baseline text-xs">
            <span className="text-muted-foreground">Maintenance fee</span>
            <span className="font-semibold text-foreground tabular-nums">${maintenance}/mo</span>
          </div>
          <p className="text-xs text-muted-foreground/60">
            Fixed. Paid to Naas. Covers agent upkeep regardless of your usage.
          </p>
        </div>
      )}

      {/* Row 2: LLM token cost — variable, paid to model provider */}
      {hasModel && (
        <div className="space-y-1.5">
          <div className="flex justify-between items-baseline text-xs">
            <span className="text-muted-foreground">LLM token cost</span>
            <span className="font-medium text-muted-foreground italic">varies with usage</span>
          </div>
          <p className="text-xs text-muted-foreground/60">
            Paid directly to {modelLabel ? `your ${modelLabel} provider` : 'your model provider'}. Not included in the maintenance fee.
          </p>
          <div className="border divide-y text-xs">
            <div className={cn('grid px-2 py-1.5 bg-muted/40 text-muted-foreground font-medium', ent ? 'grid-cols-4' : 'grid-cols-3')}>
              <span>Tier</span>
              <span className="text-center">Queries/mo</span>
              <span className="text-right">LLM cost</span>
              {ent && <span className="text-right text-blue-600">TCO</span>}
            </div>
            {cfg.usage_tiers.map(({ label, interactions, avg_tokens, description }) => {
              const llmCost = mod.model ? llmCostForTier(mod.model, interactions, avg_tokens, cfg) : null;
              const tco = ent && llmCost !== null ? maintenance + llmCost : null;
              return (
                <div key={label} className={cn('grid px-2 py-1.5', ent ? 'grid-cols-4' : 'grid-cols-3')}>
                  <span className="font-medium text-foreground">{label}</span>
                  <span className="text-center text-muted-foreground/80">{description}</span>
                  <span className="text-right tabular-nums text-muted-foreground">
                    {llmCost !== null ? formatUSD(llmCost) : 'N/A'}
                  </span>
                  {ent && (
                    <span className="text-right tabular-nums font-semibold text-blue-600">
                      {tco !== null ? formatUSD(tco) : `$${maintenance}/mo`}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          {ent && (
            <p className="text-xs text-muted-foreground/60">
              TCO = ${maintenance}/mo maintenance{!mod.functional ? ` (early access rate, standard is $${cfg.pricing.maintenance_standard_usd}/mo)` : ''} + LLM tokens billed by your model provider.
            </p>
          )}
        </div>
      )}

      {/* What the maintenance fee covers */}
      {ent && (
        <div className="border-t pt-2.5 space-y-1.5">
          <p className="text-xs font-semibold text-foreground">What your expert retainer covers</p>
          <ul className="space-y-1 text-xs text-muted-foreground">
            {[
              'Dedicated AI engineer continuously refining domain knowledge and system prompts',
              'Model migration when the underlying LLM is deprecated, updated, or repriced',
              'Regulatory and standards monitoring — prompts updated when rules change',
              'Tool and API integrations patched as third-party services evolve',
              'Ontology and knowledge graph connections kept current',
              'Regression testing after every model or platform change',
            ].map((item) => (
              <li key={item} className="flex items-start gap-1.5">
                <span className="mt-0.5 text-blue-500 shrink-0">+</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground/60 pt-0.5">
            Not a license. Not a SaaS subscription. A retainer for the expert who keeps this agent production-ready. The agent itself is MIT licensed and yours to fork.
          </p>
        </div>
      )}
      {!ent && (
        <p className="text-xs text-muted-foreground/60 border-t pt-2">
          Community tier. MIT licensed, self-hosted, self-maintained. LLM costs are your only expense.
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
  { id: 'docs', name: 'Docs', description: 'Rich text editor for documentation, notes, and runbooks with agent assistance.', icon: <FileText size={22} />, type: 'applications', status: 'coming-soon' },
  { id: 'slides', name: 'Slides', description: 'Build and narrate presentations driven by your knowledge graph.', icon: <Presentation size={22} />, type: 'applications', status: 'coming-soon' },
  { id: 'sheets', name: 'Sheets', description: 'Intelligent spreadsheets with formula support and live data connectors.', icon: <Table2 size={22} />, type: 'applications', status: 'coming-soon' },
  { id: 'board', name: 'Board', description: 'Kanban boards and whiteboards to manage tasks and visual workflows.', icon: <Trello size={22} />, type: 'applications', status: 'coming-soon' },
  { id: 'calendar', name: 'Calendar', description: 'Schedule and timeline management synced with your agents.', icon: <Calendar size={22} />, type: 'applications', status: 'coming-soon' },
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

function ModuleCard({ mod, onClick, cfg }: { mod: ModuleInfo; onClick: () => void; cfg: MarketplaceConfig }) {
  const isPortrait = mod.category === 'domain';
  const pricing = getModulePricing(mod, cfg);

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

function AgentIdCard({ mod, onClose, cfg, workspaceId }: { mod: ModuleInfo; onClose: () => void; cfg: MarketplaceConfig; workspaceId: string | null }) {
  const isPortrait = mod.category === 'domain';
  const pricing = getModulePricing(mod, cfg);

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
            <TcoBadge mod={mod} cfg={cfg} />

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

            {/* Open in Apps — only for installed modules that have a launchable app */}
            {mod.installed && mod.app_url && workspaceId && (
              <Link
                href={`/workspace/${workspaceId}/apps?open=${encodeURIComponent(mod.module_path)}`}
                className="flex w-full items-center justify-center gap-2 py-2.5 text-sm font-semibold border border-workspace-accent/40 text-workspace-accent hover:bg-workspace-accent/10 transition-colors"
              >
                <AppWindow size={14} />
                Open in Apps
              </Link>
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
  const { currentWorkspaceId } = useWorkspaceStore();

  const [typeFilter, setTypeFilter] = useState<ArtifactType>(() => {
    const t = searchParams?.get('type') as ArtifactType | null;
    return t && ALL_TYPES.includes(t) ? t : 'all';
  });
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');
  const [data, setData] = useState<ModulesResponse | null>(null);
  const [mktCfg, setMktCfg] = useState<MarketplaceConfig>(DEFAULT_MARKETPLACE_CONFIG);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMod, setSelectedMod] = useState<ModuleInfo | null>(null);

  useEffect(() => {
    const t = searchParams?.get('type') as ArtifactType | null;
    if (t && ALL_TYPES.includes(t)) setTypeFilter(t);
  }, [searchParams]);

  useEffect(() => {
    const apiBase = getApiUrl();
    setLoading(true);
    Promise.all([
      authFetch(`${apiBase}/api/modules/`).then((r) => (r.ok ? r.json() : Promise.reject(r.statusText))),
      authFetch(`${apiBase}/api/modules/config`).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([modules, cfgRes]: [ModulesResponse, { config: MarketplaceConfig } | null]) => {
        setData(modules);
        if (cfgRes?.config) setMktCfg(cfgRes.config);
      })
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
      type: 'applications' as ArtifactType,
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
                        <ModuleCard key={mod.module_path} mod={mod} onClick={() => setSelectedMod(mod)} cfg={mktCfg} />
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
        <AgentIdCard mod={selectedMod} onClose={() => setSelectedMod(null)} cfg={mktCfg} workspaceId={currentWorkspaceId} />
      )}
    </div>
  );
}
