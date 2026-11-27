'use client';

import { List } from 'lucide-react';
import { DOCUMENTS_KIND } from '@/components/office/office-kinds';
import { DocumentsOutline } from '@/components/documents/documents-filmstrip';
import { clampSectionIndex, parseDocumentsOutline } from '@/components/documents/documents-outline';
import { openDocumentsAgentPane } from '@/lib/create-documents-project';
import { patchDocumentsProject } from '@/lib/documents-project-actions';
import { DOCUMENTS_UPDATED_EVENT, useDocumentsStore, type DocumentsSidebarView } from '@/stores/documents';
import { OfficeSection, type OfficeSectionConfig } from './office-section';

export const DOCUMENTS_SECTION: OfficeSectionConfig<DocumentsSidebarView> = {
  kind: DOCUMENTS_KIND,
  useStore: useDocumentsStore,
  updatedEvent: DOCUMENTS_UPDATED_EVENT,
  label: 'Documents',
  description: 'Documents in this workspace',
  views: {
    tree: { id: 'documents', label: 'Documents' },
    detail: {
      id: 'outline',
      label: 'Outline',
      icon: <List size={14} />,
      loading: 'Loading sections…',
      empty: 'Open a document to see its sections.',
    },
  },
  newItem: { label: 'New document', title: 'New document' },
  create: { overlay: 'document' },
  patch: patchDocumentsProject,
  openAgentPane: openDocumentsAgentPane,
  recoverList: true,
};

/** Documents sidebar: the file tree, or the open document's headings. */
export function DocumentsSection(props: { collapsed: boolean; detailOnly?: boolean }) {
  const outline = useDocumentsStore((s) => s.outline);
  const selectedIndex = useDocumentsStore((s) => s.selectedIndex);
  const setSelectedIndex = useDocumentsStore((s) => s.setSelectedIndex);
  const reorder = useDocumentsStore((s) => s.reorderOpenDocument);
  return (
    <OfficeSection
      {...props}
      config={DOCUMENTS_SECTION}
      hasOpenSession={Boolean(outline)}
      renderDetail={() => {
        if (!outline?.html) return null;
        const sections = parseDocumentsOutline(outline.html);
        return (
          <DocumentsOutline
            html={outline.html}
            workspaceId={outline.workspaceId}
            slug={outline.slug}
            sections={sections}
            selectedIndex={clampSectionIndex(selectedIndex, sections.length)}
            disabled={outline.disabled}
            onSelect={setSelectedIndex}
            onReorder={(fromIndex, toIndex) => reorder?.(fromIndex, toIndex)}
          />
        );
      }}
    />
  );
}
