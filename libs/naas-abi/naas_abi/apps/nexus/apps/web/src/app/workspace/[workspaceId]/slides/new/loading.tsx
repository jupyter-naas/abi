import { OfficeCreateLoader } from '@/components/office/office-create-loader';

export default function NewSlidesLoading() {
  return <OfficeCreateLoader kind="deck" phase="creating" />;
}
