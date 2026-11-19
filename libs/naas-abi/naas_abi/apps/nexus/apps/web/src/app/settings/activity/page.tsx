import { redirect } from 'next/navigation';
import { systemViewPath } from '../system/system-tabs';

export default function ActivityIndexPage() {
  redirect(systemViewPath('traffic'));
}
