'use client';

import { useParams } from 'next/navigation';
import { SectionServicePage } from '../../system/data/service-page';

export default function DataServicePage() {
  const params = useParams<{ service: string }>();
  return <SectionServicePage section="data" slug={params?.service ?? ''} />;
}
