'use client';

import Link from 'next/link';
import { ArrowLeft, ExternalLink, Loader2 } from 'lucide-react';
import { formatPeriod, type TopicDetail, type TopicSectionResult } from '@/lib/search-topics';
import { SparqlDisclosure } from './sparql-disclosure';
import { TopicAvatar } from './topic-avatar';

/**
 * Detail of one individual: the header-role slots, every extra header variable
 * as a fact, then one block per section. A section with no rows shows its
 * configured empty text — "nothing recorded" and "failed to load" never look alike.
 */
export function TopicDetailView({ detail, loading, error, backHref, linkFor }: {
  detail: TopicDetail | null;
  loading: boolean;
  error: string | null;
  backHref: string;
  linkFor: (topicId: string, uri: string) => string;
}) {
  if (loading && !detail) {
    return <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground" role="status"><Loader2 size={14} className="animate-spin" /> Loading…</div>;
  }
  if (error) {
    return (
      <div className="space-y-3 p-2">
        <BackLink href={backHref} />
        <div role="alert" className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">{error}</div>
      </div>
    );
  }
  if (!detail) return null;

  return (
    <article className="space-y-5">
      <BackLink href={backHref} />
      <header className="flex gap-4">
        <TopicAvatar label={detail.title} image={detail.image} size={72} className="rounded-xl" />
        <div className="min-w-0 flex-1 space-y-1">
          <h2 className="text-xl font-semibold leading-tight">{detail.title}</h2>
          {detail.subtitle && <p className="text-sm text-muted-foreground">{detail.subtitle}</p>}
          <div className="flex flex-wrap items-center gap-3 pt-1 text-xs text-muted-foreground">
            <span className="truncate font-mono" title={detail.uri}>{detail.uri}</span>
            {detail.url && /^https?:\/\//i.test(detail.url) && (
              <a href={detail.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-workspace-accent hover:underline">
                Source <ExternalLink size={11} />
              </a>
            )}
          </div>
        </div>
      </header>

      {detail.snippet && <p className="whitespace-pre-line text-sm leading-relaxed">{detail.snippet}</p>}

      {detail.facts.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border bg-card p-3 text-sm sm:grid-cols-4">
          {detail.facts.map(fact => (
            <div key={fact.key} className="min-w-0">
              <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{fact.label}</dt>
              <dd className="truncate" title={fact.value}>{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}
      <SparqlDisclosure sparql={detail.header_sparql} />

      {detail.sections.map(section => <Section key={section.id} section={section} linkFor={linkFor} />)}
    </article>
  );
}

function BackLink({ href, className }: { href: string; className?: string }) {
  return (
    <Link href={href} scroll={false} className={`inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground ${className || ''}`}>
      <ArrowLeft size={12} /> Back to results
    </Link>
  );
}

function Section({ section, linkFor }: { section: TopicSectionResult; linkFor: (topicId: string, uri: string) => string }) {
  // Rows with only a title (skills, tags…) read better as chips than as a list.
  const compact = section.items.length > 0 && section.items.every(i => !i.subtitle && !i.snippet && !i.start && !i.end && !i.tags?.length);
  return (
    <section className="space-y-2 border-t pt-4">
      <h3 className="text-sm font-semibold">
        {section.label}
        {section.items.length > 0 && <span className="ml-2 text-xs font-normal text-muted-foreground">{section.items.length}</span>}
      </h3>

      {section.error ? (
        <p role="alert" className="text-sm text-red-500">This section could not be loaded: {section.error}</p>
      ) : section.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{section.empty_text}</p>
      ) : compact ? (
        <div className="flex flex-wrap gap-1.5">
          {section.items.map((item, i) => {
            const chip = 'bg-secondary px-2 py-0.5 text-xs';
            return section.link_topic && item.item
              ? <Link key={i} href={linkFor(section.link_topic, item.item)} className={`${chip} hover:text-workspace-accent`}>{item.title}</Link>
              : <span key={i} className={chip}>{item.title}</span>;
          })}
        </div>
      ) : (
        <ol className="space-y-3">
          {section.items.map((item, i) => {
            const period = formatPeriod(item.start, item.end);
            const subtitle = item.subtitle && section.link_topic && item.item
              ? <Link href={linkFor(section.link_topic, item.item)} className="text-workspace-accent hover:underline">{item.subtitle}</Link>
              : item.subtitle;
            return (
              <li key={i} className="flex gap-3">
                <TopicAvatar label={item.subtitle || item.title} image={item.image} size={32} />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">
                    {!item.subtitle && section.link_topic && item.item
                      ? <Link href={linkFor(section.link_topic, item.item)} className="hover:text-workspace-accent hover:underline">{item.title}</Link>
                      : item.title}
                  </div>
                  {subtitle && <div className="text-xs">{subtitle}</div>}
                  {period && <div className="text-xs text-muted-foreground">{period}</div>}
                  {item.snippet && (
                    item.snippet.includes('\n')
                      ? <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
                          {item.snippet.split('\n').filter(Boolean).map((line, j) => <li key={j}>{line}</li>)}
                        </ul>
                      : <p className="mt-1 text-xs text-muted-foreground">{item.snippet}</p>
                  )}
                  {item.tags && item.tags.length > 0 && (
                    <ul className="mt-1.5 flex flex-wrap gap-1" aria-label="Skills and languages">
                      {item.tags.map(tag => <li key={tag} className="bg-secondary px-1.5 py-0.5 text-[11px]">{tag}</li>)}
                    </ul>
                  )}
                  {item.url && /^https?:\/\//i.test(item.url) && (
                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs text-workspace-accent hover:underline">
                      Source <ExternalLink size={10} />
                    </a>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
      <SparqlDisclosure sparql={section.sparql} />
    </section>
  );
}
