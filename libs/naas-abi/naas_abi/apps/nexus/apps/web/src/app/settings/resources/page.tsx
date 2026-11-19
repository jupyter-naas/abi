import { redirect } from 'next/navigation';
import { servicePagePath, servicePagesIn } from '../lib/service-pages';

export default function ResourcesIndexPage() {
  redirect(servicePagePath(servicePagesIn('resources')[0].service));
}
