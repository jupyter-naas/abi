'use client';

import { BarList } from '../bar-list';
import { Card } from '../card';
import { formatNumber } from '../format';
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../states';
import { useAnalytics } from '../use-analytics';
import type { AnalyticsTabProps } from '../tabs';
import type { PagesResponse } from '../types';

export function PagesTab({ scope, filters }: AnalyticsTabProps) {
  const { data, loading, error } = useAnalytics<PagesResponse>(scope, '/pages', filters);
  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  const pages = data?.pages ?? [];
  return (
    <Card title="Pages" subtitle="Page views and unique visitors">
      {pages.length === 0 ? (
        <EmptyBlock>No page views in this period.</EmptyBlock>
      ) : (
        <BarList
          items={pages.map((p) => ({
            key: p.page_path,
            label: p.page_title,
            sublabel: `${p.page_path} · ${p.unique_users} unique users`,
            value: p.views,
          }))}
          valueLabel={(v) => `${formatNumber(v)} views`}
        />
      )}
    </Card>
  );
}
