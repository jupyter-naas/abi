from naas_abi.agents.feature import (
    FEATURE_RECURSION_LIMIT,
    build_feature_agent,
    configured_feature_model,
    feature_handoff_intents,
    feature_system_prompt,
)
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
)

_WEB = "naas_abi/apps/nexus/apps/web/src"
_API = "naas_abi/apps/nexus/apps/api/app"

FILES_CODE_MAP = f"""Web:
- {_WEB}/app/workspace/[workspaceId]/files/browse/browse.tsx: the file browser (drives, folders, paging, search, upload, rename, delete, preview).
- {_WEB}/app/workspace/[workspaceId]/files/page.tsx and files/lib/files-route.ts: desktop vs mobile routing, ?source=&path= deep links.
- {_WEB}/app/workspace/[workspaceId]/files/lib/drive-label.ts: drive names (My drive, workspace drive, platform, system).
- {_WEB}/stores/files.ts: currentPath, activeSource (drive), open files, fetches to /api/files.
- {_WEB}/components/files/pdf-viewer.tsx: PDF preview.
- {_WEB}/components/shell/sidebar/files-section.tsx and {_WEB}/app/workspace/[workspaceId]/settings/drives/page.tsx: drives sidebar and drive settings.
API:
- {_API}/services/files/adapters/primary/files__primary_adapter__FastAPI.py: /api/files routes (list, create, folder, rename, upload, preview/pdf, archive, raw, read, update, delete) and per-scope authorization (_authorize_path).
- {_API}/services/files/service.py: FilesService over object storage (list with paging/search/sort, read text, write, rename, upload limits, PDF preview, zip archive).
- {_API}/services/files/drive_roots.py: object-storage layout: my-drive/<user>, workspace-drive/<workspace>, platform-drive under the module root, plus the system drive.
- {_API}/services/files/legacy_storage_migration.py: moves legacy paths into the drive layout.
- {_API}/services/files/files__schema.py: FileInfoData, errors (AlreadyExists, NotFound, NotText, UploadTooLarge).
Engine: naas_abi_core/services/object_storage/ (ObjectStorageService; MinIO/S3 and local adapters).
Agent: naas_abi/agents/FilesAgent.py and naas_abi/agents/tools/files_tools.py."""

FILES_CAPABILITIES = """- Browse drives: My drive (yours only), the workspace drive (every member), and the platform and system drives when the workspace enables them in Settings > Drives.
- Folders and files: create, upload, rename or move, delete, download a folder as a zip, preview PDFs and office files, edit text files.
- Search names in a folder, sort by name, size, or modified, page long folders.
- I can list folders, read text files, and create or overwrite text files in the workspace drive or My drive.
- Feature flag `files` (on for every role by default). All storage is object storage under naas_abi/."""

_HANDOFF_PHRASES = (
    "list my files",
    "open this file",
    "read the file",
    "create a text file",
    "what is in the workspace drive",
    "liste mes fichiers",
    "lis ce fichier",
    "crée un fichier texte",
    "que contient le drive",
)


class FilesAgent(IntentAgent):
    """Office agent for Nexus Files (workspace object storage).

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi FilesAgent
    """

    name: str = "Files"
    description: str = (
        "Office agent for Nexus Files. Lists folders, reads and writes text "
        "files in the workspace drive and My drive, and explains drives, "
        "uploads, previews, and how Files is built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Files",
        class_name="FilesAgent",
        feature="Files",
        role="You work on the workspace's files and explain the file browser.",
        context=(
            "On the Files page you receive an open-feature block (feature: files, "
            "and open_file_id or open_folder_id with the storage path, prefixed my_drive: for My drive, when "
            "something is open). Tools default to it. A bare file name lands in "
            "the open folder."
        ),
        tasks="""1. "What can I do here?": answer from <capabilities>, tied to the open folder (list_files).
2. "How is it built?": read <code_map> files first, then explain with paths.
3. Operating: list_files, read_text_file, write_text_file (create; overwrite only when the user asked to replace).
4. Uploads, rename, delete, PDF preview, zip download: explain the UI flow and route; you have no tools for those.""",
        capabilities=FILES_CAPABILITIES,
        code_map=FILES_CODE_MAP,
        constraints="- Never overwrite a file unless the user asked to replace it.",
    )
    suggestions: list[dict] = [
        {"label": "What can you do?", "value": "What can I do in Files?"},
        {
            "label": "How is it built?",
            "value": "How are drives and storage paths implemented? Read the code and cite files.",
        },
        {"label": "This folder", "value": "What is in the open folder?"},
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Files", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.agents.tools.files_tools import files_tools
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools

        return files_tools() + nexus_source_tools()

    @classmethod
    def get_chat_model_id(cls) -> str:
        return configured_feature_model()

    @classmethod
    def get_chat_model_ids(cls) -> list[str]:
        return [configured_feature_model()]

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
        model_id: str | None = None,
    ) -> "FilesAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
