import { OfficeCreateLoader } from '@/components/office/office-create-loader';

export default function NewPresentationLoading() {
  return <OfficeCreateLoader kind="deck" phase="creating" />;
}
