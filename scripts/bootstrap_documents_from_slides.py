#!/usr/bin/env python3
"""Bootstrap Nexus Documents feature from Slides (one-time generator)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABI = ROOT / "libs/naas-abi/naas_abi"
NEXUS_API = ABI / "apps/nexus/apps/api/app"
NEXUS_WEB = ABI / "apps/nexus/apps/web/src"

# (source, destination) file or directory copies with optional rename
COPY_MAP: list[tuple[Path, Path]] = [
    (
        NEXUS_API / "services/slides",
        NEXUS_API / "services/documents",
    ),
    (
        ABI / "agents/slides",
        ABI / "agents/documents",
    ),
    (ABI / "agents/SlidesAgent.py", ABI / "agents/DocumentsAgent.py"),
    (ABI / "agents/SlidesAgent_test.py", ABI / "agents/DocumentsAgent_test.py"),
    (ABI / "agents/AbiAgent_slides_test.py", ABI / "agents/AbiAgent_documents_test.py"),
    (ABI / "agents/tools/slides_tools.py", ABI / "agents/tools/documents_tools.py"),
    (ABI / "agents/tools/slides_tools_test.py", ABI / "agents/tools/documents_tools_test.py"),
    (
        NEXUS_WEB / "stores/slides.ts",
        NEXUS_WEB / "stores/documents.ts",
    ),
    (
        NEXUS_WEB / "stores/slides.test.ts",
        NEXUS_WEB / "stores/documents.test.ts",
    ),
    (
        NEXUS_WEB / "lib/create-slides-project.ts",
        NEXUS_WEB / "lib/create-documents-project.ts",
    ),
    (
        NEXUS_WEB / "lib/create-slides-project.test.ts",
        NEXUS_WEB / "lib/create-documents-project.test.ts",
    ),
    (
        NEXUS_WEB / "lib/slides-project-actions.ts",
        NEXUS_WEB / "lib/documents-project-actions.ts",
    ),
    (
        NEXUS_WEB / "lib/slides-project-actions.test.ts",
        NEXUS_WEB / "lib/documents-project-actions.test.ts",
    ),
    (
        NEXUS_WEB / "lib/slides-templates.ts",
        NEXUS_WEB / "lib/documents-templates.ts",
    ),
    (
        NEXUS_WEB / "lib/slides-templates.test.ts",
        NEXUS_WEB / "lib/documents-templates.test.ts",
    ),
    (
        NEXUS_WEB / "lib/slides-pane-conversation.ts",
        NEXUS_WEB / "lib/documents-pane-conversation.ts",
    ),
    (
        NEXUS_WEB / "lib/slides-pane-conversation.test.ts",
        NEXUS_WEB / "lib/documents-pane-conversation.test.ts",
    ),
    (
        NEXUS_WEB / "lib/slides-my-drive.ts",
        NEXUS_WEB / "lib/documents-my-drive.ts",
    ),
    (
        NEXUS_WEB / "lib/slides-my-drive.test.ts",
        NEXUS_WEB / "lib/documents-my-drive.test.ts",
    ),
    (
        NEXUS_WEB / "components/slides",
        NEXUS_WEB / "components/documents",
    ),
    (
        NEXUS_WEB / "components/shell/sidebar/slides-section.tsx",
        NEXUS_WEB / "components/shell/sidebar/documents-section.tsx",
    ),
    (
        NEXUS_WEB / "components/shell/sidebar/slides-section.test.ts",
        NEXUS_WEB / "components/shell/sidebar/documents-section.test.ts",
    ),
    (
        NEXUS_WEB / "components/shell/sidebar/slides-section-views.ts",
        NEXUS_WEB / "components/shell/sidebar/documents-section-views.ts",
    ),
    (
        NEXUS_WEB / "components/shell/sidebar/slides-tree.ts",
        NEXUS_WEB / "components/shell/sidebar/documents-tree.ts",
    ),
    (
        NEXUS_WEB / "components/shell/sidebar/slides-tree.test.ts",
        NEXUS_WEB / "components/shell/sidebar/documents-tree.test.ts",
    ),
    (
        NEXUS_WEB / "components/shell/sidebar/slides-tree-view.tsx",
        NEXUS_WEB / "components/shell/sidebar/documents-tree-view.tsx",
    ),
    (
        NEXUS_WEB / "components/shell/sidebar/slides-tree-view.test.ts",
        NEXUS_WEB / "components/shell/sidebar/documents-tree-view.test.ts",
    ),
    (
        NEXUS_WEB / "components/chat/slides-composer-model.ts",
        NEXUS_WEB / "components/chat/documents-composer-model.ts",
    ),
    (
        NEXUS_WEB / "components/chat/slides-composer-model.test.ts",
        NEXUS_WEB / "components/chat/documents-composer-model.test.ts",
    ),
    (
        NEXUS_WEB / "components/chat/slides-empty-state.ts",
        NEXUS_WEB / "components/chat/documents-empty-state.ts",
    ),
    (
        NEXUS_WEB / "components/chat/slides-empty-state.test.ts",
        NEXUS_WEB / "components/chat/documents-empty-state.test.ts",
    ),
    (
        NEXUS_WEB / "app/workspace/[workspaceId]/slides",
        NEXUS_WEB / "app/workspace/[workspaceId]/documents",
    ),
    (
        NEXUS_API
        / "services/chat/adapters/primary/chat__primary_adapter__streaming_slides_test.py",
        NEXUS_API
        / "services/chat/adapters/primary/chat__primary_adapter__streaming_documents_test.py",
    ),
    (ABI / "apps/nexus/assets/slides", ABI / "apps/nexus/assets/documents"),
]

RENAME_IN_COPIED: list[tuple[str, str]] = [
    ("slides__primary_adapter__FastAPI.py", "documents__primary_adapter__FastAPI.py"),
    ("slides__primary_adapter__FastAPI_test.py", "documents__primary_adapter__FastAPI_test.py"),
]

# Order matters: longest / most specific first.
REPLACEMENTS: list[tuple[str, str]] = [
    ("pickSlidesOfficeAgent", "pickDocumentsOfficeAgent"),
    ("openSlidesAgentPane", "openDocumentsAgentPane"),
    ("isNexusSlidesAgent", "isNexusDocumentsAgent"),
    ("SlidesOfficeAgent", "DocumentsOfficeAgent"),
    ("pick_workspace_slides_agent_id", "pick_workspace_documents_agent_id"),
    ("lookup_slides_sidecar", "lookup_documents_sidecar"),
    ("_render_slides_context_block", "_render_documents_context_block"),
    ("isSlidesWriteTool", "isDocumentsWriteTool"),
    ("SLIDES_DECK_UPDATED_EVENT", "DOCUMENTS_UPDATED_EVENT"),
    ("SlidesDeckUpdatedDetail", "DocumentsUpdatedDetail"),
    ("SlidesDeckSource", "DocumentsSource"),
    ("create_slides_project", "create_documents_project"),
    ("list_slides_projects", "list_documents_projects"),
    ("list_slides_sections", "list_document_sections"),
    ("read_slides_section", "read_document_section"),
    ("write_slides_sections", "write_document_sections"),
    ("write_slides_section", "write_document_section"),
    ("replace_in_slides_deck", "replace_in_document"),
    ("read_slides_deck", "read_document"),
    ("write_slides_deck", "write_document"),
    ("reject_repeat_list_slides_sections", "reject_repeat_list_document_sections"),
    ("reject_unresearched_slides_write", "reject_unresearched_documents_write"),
    ("reject_slides_section_read", "reject_documents_section_read"),
    ("note_slides_section_read", "note_documents_section_read"),
    ("note_slides_web_search", "note_documents_web_search"),
    ("note_slides_list", "note_documents_list"),
    ("slides_brief_requires_research", "documents_brief_requires_research"),
    ("slides_creation_requested", "documents_creation_requested"),
    ("slides_search_budget_remaining", "documents_search_budget_remaining"),
    ("slides_search_tool_bound", "documents_search_tool_bound"),
    ("validate_configured_slides_model", "validate_configured_documents_model"),
    ("apply_slides_model_override", "apply_documents_model_override"),
    ("attach_slides_research_note", "attach_documents_research_note"),
    ("bind_slides_research_policy", "bind_documents_research_policy"),
    ("bind_slides_reasoning", "bind_documents_reasoning"),
    ("configured_slides_model", "configured_documents_model"),
    ("load_slides_chat_model", "load_documents_chat_model"),
    ("resolve_slides_llm_model", "resolve_documents_llm_model"),
    ("slides_research_tools", "documents_research_tools"),
    ("is_placeholder_deck_title", "is_placeholder_document_title"),
    ("derive_deck_title", "derive_document_title"),
    ("resolve_deck_title", "resolve_document_title"),
    ("insert_slide", "insert_section"),
    ("delete_slide", "delete_section"),
    ("duplicate_slide", "duplicate_section"),
    ("reorder_slides", "reorder_sections"),
    ("SlidesAgent", "DocumentsAgent"),
    ("slides_tools", "documents_tools"),
    ("abi_slides_agent_model", "abi_documents_agent_model"),
    ("ABI_SLIDES_TEMPLATE_NAMESPACE", "ABI_DOCUMENTS_TEMPLATE_NAMESPACE"),
    ("ABI_SLIDES_TEMPLATE", "ABI_DOCUMENTS_TEMPLATE"),
    ("slides_template_sources", "documents_template_sources"),
    ("SlidesTemplateSourceConfig", "DocumentsTemplateSourceConfig"),
    ("SlidesTemplateSource", "DocumentsTemplateSource"),
    ("SLIDES_RECURSION_LIMIT", "DOCUMENTS_RECURSION_LIMIT"),
    ("slides_active_slug", "documents_active_slug"),
    ("slides_active_title", "documents_active_title"),
    ("slides_active_mode", "documents_active_mode"),
    ("slides_research_required", "documents_research_required"),
    ("slides_research_queries", "documents_research_queries"),
    ("slides_creation_intent", "documents_creation_intent"),
    ("slides_writes_completed", "documents_writes_completed"),
    ("slides_list_calls", "documents_list_calls"),
    ("slides_section_read_indexes", "documents_section_read_indexes"),
    ("note_slides_write", "note_documents_write"),
    ("slides_turn_active", "documents_turn_active"),
    ("slides_step_limit_message", "documents_step_limit_message"),
    ("MAX_SLIDES_SECTION_READS", "MAX_DOCUMENTS_SECTION_READS"),
    ("MAX_SLIDES_SEARCHES", "MAX_DOCUMENTS_SEARCHES"),
    ("DEFAULT_SLIDES_MODEL", "DEFAULT_DOCUMENTS_MODEL"),
    ("SLIDES_GUIDELINES", "DOCUMENTS_GUIDELINES"),
    ("startNewPresentation", "startNewDocument"),
    ("copyDeckToMyDrive", "copyDocumentToMyDrive"),
    ("slidesPaneConversationByKey", "documentsPaneConversationByKey"),
    ("SlidesPaneConversation", "DocumentsPaneConversation"),
    ("SlidesSeedTemplate", "DocumentsSeedTemplate"),
    ("slidesApiErrorMessage", "documentsApiErrorMessage"),
    ("SlidesProjectMenu", "DocumentsProjectMenu"),
    ("SlidesIndexGallery", "DocumentsIndexGallery"),
    ("SlidesDeckCardView", "DocumentsCardView"),
    ("SlidesDeckCard", "DocumentsCard"),
    ("SlidesPreviewFrameHandle", "DocumentsPreviewFrameHandle"),
    ("SlidesPreviewFrame", "DocumentsPreviewFrame"),
    ("SlidesMenuBar", "DocumentsMenuBar"),
    ("SlidesStatusBar", "DocumentsStatusBar"),
    ("SlidesFilmstrip", "DocumentsOutline"),
    ("SlidesEditorMode", "DocumentsEditorMode"),
    ("SlidesSidebarView", "DocumentsSidebarView"),
    ("SlidesFilmstripDeck", "DocumentsOutlineDoc"),
    ("SlidesRuntimeStatus", "DocumentsRuntimeStatus"),
    ("SlidesProject", "DocumentsProject"),
    ("useSlidesStore", "useDocumentsStore"),
    ("isSlidesNestedPath", "isDocumentsNestedPath"),
    ("isSlidesTypingTarget", "isDocumentsTypingTarget"),
    ("downloadSlidesHtml", "downloadDocumentsHtml"),
    ("resolveSlidesPreviewAssets", "resolveDocumentsPreviewAssets"),
    ("applySlidesTextEdits", "applyDocumentsTextEdits"),
    ("collectSlidesTextEdits", "collectDocumentsTextEdits"),
    ("sanitizeSlidesEditHtml", "sanitizeDocumentsEditHtml"),
    ("SLIDES_MANUAL_EDIT_IDLE_MS", "DOCUMENTS_MANUAL_EDIT_IDLE_MS"),
    ("SlidesTextEdit", "DocumentsTextEdit"),
    ("clampSlideIndex", "clampSectionIndex"),
    ("deleteSlide", "deleteSection"),
    ("duplicateSlide", "duplicateSection"),
    ("insertSlide", "insertSection"),
    ("parseSlidesOutline", "parseDocumentsOutline"),
    ("reorderSlides", "reorderSections"),
    ("SlideLayout", "SectionLayout"),
    ("SlideMutationResult", "SectionMutationResult"),
    ("SlideOutlineItem", "SectionOutlineItem"),
    ("ensureSlidesRuntime", "ensureDocumentsRuntime"),
    ("SlidesSection", "DocumentsSection"),
    ("slides-section", "documents-section"),
    ("slides-tree-view", "documents-tree-view"),
    ("slides-tree", "documents-tree"),
    ("slides-project-menu", "documents-project-menu"),
    ("slides-index-gallery", "documents-index-gallery"),
    ("slides-deck-card", "documents-card"),
    ("slides-preview-frame", "documents-preview-frame"),
    ("slides-preview-fit", "documents-preview-fit"),
    ("slides-menu-bar", "documents-menu-bar"),
    ("slides-status-bar", "documents-status-bar"),
    ("slides-filmstrip", "documents-outline"),
    ("slides-outline", "documents-outline-api"),
    ("slides-pptx-from-dom", "documents-pdf-from-dom"),
    ("slides-assets", "documents-assets"),
    ("slides-composer-model", "documents-composer-model"),
    ("slides-empty-state", "documents-empty-state"),
    ("setDeckDirty", "setDocumentDirty"),
    ("setDeckSource", "setDocumentSource"),
    ("requestDeckRefresh", "requestDocumentRefresh"),
    ("deckDirty", "documentDirty"),
    ("deckSource", "documentSource"),
    ("deck_path", "document_path"),
    ("deck.html", "document.html"),
    ("slideCount", "sectionCount"),
    ("setSlideCount", "setSectionCount"),
    ("filmstrip", "outline"),
    ("setFilmstrip", "setOutline"),
    ("sidebarView", "sidebarView"),
    ("'decks'", "'documents'"),
    ("'filmstrip'", "'outline'"),
    ("abi-slides", "abi-documents"),
    ("nexus-slides-template", "nexus-documents-template"),
    ("nexus-slides", "nexus-documents"),
    ("_SLIDES_", "_DOCUMENTS_"),
    ("slides_brief", "documents_brief"),
    ("/api/slides", "/api/documents"),
    ("/slides", "/documents"),
    ("feature: 'slides'", "feature: 'documents'"),
    ("useFeature('slides')", "useFeature('documents')"),
    ("'slides'", "'documents'"),
    ("slides/", "documents/"),
    ("slides.", "documents."),
    ("Slides ", "Documents "),
    ("Slides,", "Documents,"),
    ("Slides.", "Documents."),
    ("Slides'", "Documents'"),
    ("Slides\"", "Documents\""),
    ("Slides\n", "Documents\n"),
    ("Slides)", "Documents)"),
    ("Slides:", "Documents:"),
    ("Slides;", "Documents;"),
    ("Slides?", "Documents?"),
    ("Slides!", "Documents!"),
    ("presentation deck", "document"),
    ("presentation decks", "documents"),
    ("slide deck", "document"),
    ("slide decks", "documents"),
    ("diaporama", "document"),
    ("présentation", "document"),
    ("presentation", "document"),
    ("deck", "document"),
    ("Deck", "Document"),
    ("slide", "section"),
    ("Slide", "Section"),
    ("PPTX", "PDF"),
    ("pptx", "pdf"),
    ("1280x720", "816px prose"),
    ("1280×720", "816px prose"),
]

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2"}


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def rename_in_tree(root: Path, old_name: str, new_name: str) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if old_name in path.name:
            path.rename(path.with_name(path.name.replace(old_name, new_name)))


def transform_text(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text


def transform_file(path: Path) -> None:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    path.write_text(transform_text(raw), encoding="utf-8")


def transform_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            transform_file(path)


def main() -> None:
    for src, dst in COPY_MAP:
        if not src.exists():
            raise SystemExit(f"Missing source: {src}")
        print(f"Copy {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")
        copy_tree(src, dst)

    docs_api = NEXUS_API / "services/documents"
    for old, new in RENAME_IN_COPIED:
        rename_in_tree(docs_api, old, new)

    # Rename slides-* component files to documents-* inside components/documents
    docs_components = NEXUS_WEB / "components/documents"
    for path in sorted(docs_components.rglob("slides-*")):
        path.rename(path.with_name(path.name.replace("slides-", "documents-", 1)))

    targets = [
        docs_api,
        ABI / "agents/documents",
        ABI / "agents/DocumentsAgent.py",
        ABI / "agents/DocumentsAgent_test.py",
        ABI / "agents/AbiAgent_documents_test.py",
        ABI / "agents/tools/documents_tools.py",
        ABI / "agents/tools/documents_tools_test.py",
        NEXUS_WEB / "stores/documents.ts",
        NEXUS_WEB / "stores/documents.test.ts",
        NEXUS_WEB / "lib",
        NEXUS_WEB / "components/documents",
        NEXUS_WEB / "components/shell/sidebar/documents-section.tsx",
        NEXUS_WEB / "components/shell/sidebar/documents-section.test.ts",
        NEXUS_WEB / "components/shell/sidebar/documents-section-views.ts",
        NEXUS_WEB / "components/shell/sidebar/documents-tree.ts",
        NEXUS_WEB / "components/shell/sidebar/documents-tree.test.ts",
        NEXUS_WEB / "components/shell/sidebar/documents-tree-view.tsx",
        NEXUS_WEB / "components/shell/sidebar/documents-tree-view.test.ts",
        NEXUS_WEB / "components/chat/documents-composer-model.ts",
        NEXUS_WEB / "components/chat/documents-composer-model.test.ts",
        NEXUS_WEB / "components/chat/documents-empty-state.ts",
        NEXUS_WEB / "components/chat/documents-empty-state.test.ts",
        NEXUS_WEB / "app/workspace/[workspaceId]/documents",
        NEXUS_API
        / "services/chat/adapters/primary/chat__primary_adapter__streaming_documents_test.py",
        ABI / "apps/nexus/assets/documents",
    ]
    for target in targets:
        if target.is_file():
            transform_file(target)
        elif target.is_dir():
            transform_tree(target)

    # handlers init
    handlers = docs_api / "handlers/__init__.py"
    handlers.write_text(
        "from naas_abi.apps.nexus.apps.api.app.services.documents.adapters.primary.documents__primary_adapter__FastAPI import (\n"
        "    router,\n"
        ")\n\n"
        "__all__ = [\"router\"]\n",
        encoding="utf-8",
    )
    print("Bootstrap complete.")


if __name__ == "__main__":
    main()
