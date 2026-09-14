import { OfficeCreateLoader } from '@/components/office/office-create-loader';

export default function NewDocumentLoading() {
  return <OfficeCreateLoader kind="document" phase="creating" />;
}
