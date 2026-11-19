import { redirect } from 'next/navigation';
import { servicePagePath, servicePagesIn } from '../lib/service-pages';

export default function DataIndexPage() {
  redirect(servicePagePath(servicePagesIn('data')[0].service));
}
