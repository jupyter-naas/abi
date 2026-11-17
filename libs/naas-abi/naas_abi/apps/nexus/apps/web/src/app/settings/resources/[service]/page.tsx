'use client';

import { useParams } from 'next/navigation';
import { SectionServicePage } from '../../system/data/service-page';

export default function ResourcesServicePage() {
  const params = useParams<{ service: string }>();
  return <SectionServicePage section="resources" slug={params?.service ?? ''} />;
}
