'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Header } from '@/components/shell/header';
import { 
  FileCode, 
  FileCode2,
  FileText,
  FileJson,
  FileImage,
  FileSpreadsheet,
  FileArchive,
  FileVideo,
  FileAudio,
  Presentation,
  Folder, 
  FolderPlus, 
  RefreshCw, 
  Upload, 
  Download, 
  Trash2,
  MoreVertical,
  Grid,
  List,
  Search,
  FlaskConical,
  Eye,
  Code,
  Star,
  X,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import {
  useFilesStore,
  type FileInfo,
  type FileSortKey,
  type SortDirection,
} from '@/stores/files';
import { authFetch, useAuthStore } from '@/stores/auth';
import { usePrompt, useConfirm } from '@/components/ui/dialogs';
import { PdfViewer } from '@/components/files/pdf-viewer';
import { FilesAddSheet } from '../components/files-add-sheet';
import { FilesMobileRow } from '../components/files-mobile-row';
import { FilesMobileToolbar } from '../components/files-mobile-toolbar';
import '../components/files-components.css';
import {
  driveLabelForSource,
  driveRootForSource,
  filesScopeForSource,
  relativeDrivePath,
} from '../lib/drive-label';
import './browse.css';

type FileWithRelativeDir = { file: File; relativeDir?: string };

async function readDirectoryEntries(
  reader: FileSystemDirectoryReader,
): Promise<FileSystemEntry[]> {
  const all: FileSystemEntry[] = [];
  while (true) {
    const batch: FileSystemEntry[] = await new Promise((resolve, reject) => {
      reader.readEntries(resolve, reject);
    });
    if (batch.length === 0) break;
    all.push(...batch);
  }
  return all;
}

async function collectEntries(
  entries: FileSystemEntry[],
  parentDir = '',
): Promise<FileWithRelativeDir[]> {
  const out: FileWithRelativeDir[] = [];
  for (const entry of entries) {
    if (entry.isFile) {
      const fileEntry = entry as FileSystemFileEntry;
      const file = await new Promise<File>((resolve, reject) => {
        fileEntry.file(resolve, reject);
      });
      out.push({ file, relativeDir: parentDir || undefined });
    } else if (entry.isDirectory) {
      const dirEntry = entry as FileSystemDirectoryEntry;
      const children = await readDirectoryEntries(dirEntry.createReader());
      const childDir = parentDir ? `${parentDir}/${entry.name}` : entry.name;
      const nested = await collectEntries(children, childDir);
      out.push(...nested);
    }
  }
  return out;
}

// Client-side sort for local synced folders (loaded whole in the browser).
// Mirrors the server ordering: case-insensitive name, numeric size, timestamp
// modified — with missing size/modified sorting first on ascending order.
function sortFiles(
  files: FileInfo[],
  sortBy: FileSortKey,
  sortDir: SortDirection,
): FileInfo[] {
  const dir = sortDir === 'desc' ? -1 : 1;
  return [...files].sort((a, b) => {
    let cmp: number;
    if (sortBy === 'size') {
      cmp = (a.size ?? -1) - (b.size ?? -1);
    } else if (sortBy === 'modified') {
      const am = a.modified ? Date.parse(a.modified) : Number.NEGATIVE_INFINITY;
      const bm = b.modified ? Date.parse(b.modified) : Number.NEGATIVE_INFINITY;
      cmp = am - bm;
    } else {
      cmp = a.name.toLowerCase().localeCompare(b.name.toLowerCase());
    }
    // Stable tiebreak by name so equal sizes/dates keep a predictable order.
    if (cmp === 0 && sortBy !== 'name') {
      cmp = a.name.toLowerCase().localeCompare(b.name.toLowerCase());
    }
    return cmp * dir;
  });
}

export default function FilesPage() {
  const router = useRouter();
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  
  const {
    files,
    loading,
    error,
    currentPath,
    filesTotal,
    filesSortBy,
    filesSortDir,
    setFilesSort,
    fetchFiles,
    createFile,
    createFolder,
    deleteFile,
    renameFile,
    uploadFile,
    uploadFiles,
    refreshFiles,
    openFile,
    activeSource,
    setActiveSource,
    syncedFolders,
    fetchLocalFiles,
    setError,
    uploadProgress,
    starredItems,
    starItem,
    unstarItem,
    starredNavigation,
    setStarredNavigation,
  } = useFilesStore();

  const { prompt, dialog: promptDialog } = usePrompt();
  const { confirm, dialog: confirmDialog } = useConfirm();
  const isMobile = useIsMobile();

  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [searchQuery, setSearchQuery] = useState('');
  // Debounced search term used to drive the server-side search fetch, so we
  // don't hit the API on every keystroke.
  const [debouncedSearch, setDebouncedSearch] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);
  // Client-side pagination: cap how many rows render at once so large folders
  // (e.g. 200+ files) don't freeze the page while the API returns everything.
  const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
  const [pageSize, setPageSize] = useState<number>(50);
  const [currentPage, setCurrentPage] = useState(1);
  // Latest page size, readable from effects without making them re-run/re-fetch.
  const pageSizeRef = useRef(pageSize);
  useEffect(() => {
    pageSizeRef.current = pageSize;
  }, [pageSize]);
  // The search term of the last fetch we issued. Updated synchronously so the
  // debounced-search effect can tell a user edit apart from a fetch that
  // navigation/mount already performed, avoiding a duplicate round-trip.
  const lastSearchRef = useRef('');
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [dropTargetPath, setDropTargetPath] = useState<string | null>(null);
  const [activeContextMenu, setActiveContextMenu] = useState<string | null>(null);
  const [addSheetOpen, setAddSheetOpen] = useState(false);
  const [toolbarMenuOpen, setToolbarMenuOpen] = useState(false);
  const [pdfViewerFileName, setPdfViewerFileName] = useState<string | null>(null);
  const [pdfViewerUrl, setPdfViewerUrl] = useState<string | null>(null);
  const [pdfViewerLoading, setPdfViewerLoading] = useState(false);
  const [pdfViewerError, setPdfViewerError] = useState<string | null>(null);
  const [pdfViewerDownloadFile, setPdfViewerDownloadFile] = useState<FileInfo | null>(null);
  const [imageViewerFileName, setImageViewerFileName] = useState<string | null>(null);
  const [imageViewerUrl, setImageViewerUrl] = useState<string | null>(null);
  const [imageViewerLoading, setImageViewerLoading] = useState(false);
  const [imageViewerError, setImageViewerError] = useState<string | null>(null);
  const [textViewerFileName, setTextViewerFileName] = useState<string | null>(null);
  const [textViewerContent, setTextViewerContent] = useState<string>('');
  const [textViewerMode, setTextViewerMode] = useState<'markdown' | 'code'>('code');
  // HTML files get a rendered preview with a toggle between preview and source.
  const [textViewerIsHtml, setTextViewerIsHtml] = useState(false);
  const [htmlPreview, setHtmlPreview] = useState(true);
  const [textViewerLoading, setTextViewerLoading] = useState(false);
  const [textViewerError, setTextViewerError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // When a starred navigation is pending, skip the regular fetch triggered by activeSource change
  const skipRegularFetchRef = useRef(false);
  // Local path of the file to auto-preview once files finish loading
  const [localPendingPreview, setLocalPendingPreview] = useState<string | null>(null);

  // Helper to open file in Lab
  const handleOpenInLab = (file: FileInfo) => {
    openFile(file.path);
    router.push(`/workspace/${workspaceId}/lab`);
  };
  
  // Close context menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setActiveContextMenu(null);
      setToolbarMenuOpen(false);
    };
    if (activeContextMenu || toolbarMenuOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [activeContextMenu, toolbarMenuOpen]);

  useEffect(() => {
    if (!addSheetOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAddSheetOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [addSheetOpen]);

  useEffect(() => {
    return () => {
      if (pdfViewerUrl) {
        URL.revokeObjectURL(pdfViewerUrl);
      }
    };
  }, [pdfViewerUrl]);

  // Close any open preview viewer when the user presses Escape.
  useEffect(() => {
    if (!pdfViewerFileName && !imageViewerFileName && !textViewerFileName) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (pdfViewerFileName) closePdfViewer();
      else if (imageViewerFileName) closeImageViewer();
      else if (textViewerFileName) closeTextViewer();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pdfViewerFileName, imageViewerFileName, textViewerFileName]);

  useEffect(() => {
    return () => {
      if (imageViewerUrl) {
        URL.revokeObjectURL(imageViewerUrl);
      }
    };
  }, [imageViewerUrl]);

  // Handle navigation triggered by clicking a starred item in the sidebar.
  // Setting skipRegularFetchRef prevents the activeSource-change effect from
  // overriding the path we set here.
  useEffect(() => {
    if (!starredNavigation) return;
    skipRegularFetchRef.current = true;
    setActiveSource(starredNavigation.source);
    setSearchQuery('');
    setDebouncedSearch('');
    lastSearchRef.current = '';
    setCurrentPage(1);
    fetchFiles(starredNavigation.path, {
      limit: pageSizeRef.current,
      offset: 0,
      search: '',
      workspaceId,
    });
    if (starredNavigation.previewPath) {
      setLocalPendingPreview(starredNavigation.previewPath);
    }
    setStarredNavigation(null);
  }, [starredNavigation, setActiveSource, fetchFiles, setStarredNavigation, workspaceId]);

  // Once the files list loads, open the pending preview (if any).
  useEffect(() => {
    if (!localPendingPreview || loading) return;
    const target = files.find((f) => f.path === localPendingPreview);
    if (!target) return;
    setLocalPendingPreview(null);
    if (isPdfFile(target)) openPdfViewer(target);
    else if (isOfficeFile(target)) openOfficePreview(target);
    else if (isImageFile(target)) openImageViewer(target);
    else if (isTextFile(target)) openTextViewer(target);
  // isPdfFile etc. are stable inline functions — listing them would cause an infinite loop
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localPendingPreview, files, loading]);
  
  // Check if we're viewing a synced local folder
  const activeSyncedFolder = syncedFolders.find((f) => f.id === activeSource);
  const isLocalFolder = !!activeSyncedFolder;
  const filesScope = filesScopeForSource(activeSource);
  const fileQueryParams = `workspace_id=${encodeURIComponent(workspaceId)}&scope=${filesScope}`;

  const authUserId = useAuthStore((state) => state.user?.id);
  const driveRoot = driveRootForSource(activeSource, workspaceId, authUserId);
  const driveLabel = driveLabelForSource(activeSource, activeSyncedFolder, isLocalFolder);
  const relativePath = relativeDrivePath(currentPath, driveRoot, activeSource, workspaceId);

  useEffect(() => {
    // Skip if a starred navigation just updated activeSource — it already called fetchFiles.
    if (skipRegularFetchRef.current) {
      skipRegularFetchRef.current = false;
      return;
    }

    if (!workspaceId) return;

    // Clear any previous errors
    setError(null);

    // Fetch files based on active source. Remote drives fetch the first page;
    // local synced folders load fully and paginate client-side.
    if (isLocalFolder && activeSyncedFolder) {
      fetchLocalFiles(activeSyncedFolder.id);
    } else {
      setSearchQuery('');
      setDebouncedSearch('');
      lastSearchRef.current = '';
      setCurrentPage(1);
      fetchFiles('', {
        limit: pageSizeRef.current,
        offset: 0,
        search: '',
        workspaceId,
      });
    }
  }, [fetchFiles, fetchLocalFiles, isLocalFolder, activeSyncedFolder, activeSource, setError, workspaceId]);

  // Drop selections that no longer exist (after navigation or deletion).
  useEffect(() => {
    setSelectedFiles((prev) => prev.filter((p) => files.some((f) => f.path === p)));
  }, [files]);

  // Warn the user before leaving while an upload is in progress.
  useEffect(() => {
    if (!uploadProgress?.active) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [uploadProgress?.active]);

  const INTERNAL_DRAG_MIME = 'application/x-nexus-file';

  const isInternalDrag = (e: React.DragEvent) =>
    e.dataTransfer.types.includes(INTERNAL_DRAG_MIME);

  // Drag and drop handlers (external upload only — internal moves bubble up but are ignored here)
  const handleDragOver = useCallback((e: React.DragEvent) => {
    if (isInternalDrag(e)) return;
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    if (isInternalDrag(e)) return;
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    if (isInternalDrag(e)) return;
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const items = e.dataTransfer.items;
    if (items && items.length > 0 && typeof items[0].webkitGetAsEntry === 'function') {
      const entries: FileSystemEntry[] = [];
      for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry();
        if (entry) entries.push(entry);
      }
      if (entries.length > 0) {
        const collected = await collectEntries(entries);
        if (collected.length > 0) {
          await uploadFiles(collected);
        }
        return;
      }
    }

    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles.length > 0) {
      await uploadFiles(droppedFiles);
    }
  }, [uploadFiles]);

  // Internal move via drag onto a folder row.
  const handleRowDragStart = (e: React.DragEvent, file: FileInfo) => {
    e.dataTransfer.setData(INTERNAL_DRAG_MIME, file.path);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleFolderDragOver = (e: React.DragEvent, folder: FileInfo) => {
    if (!isInternalDrag(e)) return;
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'move';
    setDropTargetPath(folder.path);
  };

  const handleFolderDragLeave = (e: React.DragEvent, folder: FileInfo) => {
    if (!isInternalDrag(e)) return;
    e.stopPropagation();
    setDropTargetPath((current) => (current === folder.path ? null : current));
  };

  const handleFolderDrop = async (e: React.DragEvent, folder: FileInfo) => {
    if (!isInternalDrag(e)) return;
    e.preventDefault();
    e.stopPropagation();
    setDropTargetPath(null);

    const sourcePath = e.dataTransfer.getData(INTERNAL_DRAG_MIME);
    if (!sourcePath) return;
    // dataTransfer.getData isn't always available during dragover, so re-validate here
    const sourceParent = sourcePath.includes('/') ? sourcePath.slice(0, sourcePath.lastIndexOf('/')) : '';
    if (
      sourcePath === folder.path ||
      sourceParent === folder.path ||
      folder.path === sourcePath ||
      folder.path.startsWith(`${sourcePath}/`)
    ) {
      return;
    }
    const name = sourcePath.includes('/') ? sourcePath.slice(sourcePath.lastIndexOf('/') + 1) : sourcePath;
    const newPath = `${folder.path}/${name}`;
    await renameFile(sourcePath, newPath);
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      await uploadFiles(selectedFiles);
      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Generate unique name if the proposed name already exists
  const getUniqueName = (baseName: string, extension: string = '') => {
    const existingNames = new Set(files.map((f) => f.name.toLowerCase()));
    let name = extension ? `${baseName}${extension}` : baseName;
    let counter = 1;
    
    while (existingNames.has(name.toLowerCase())) {
      name = extension ? `${baseName}-${counter}${extension}` : `${baseName}-${counter}`;
      counter++;
    }
    return name;
  };

  const handleNewFile = async () => {
    const defaultName = getUniqueName('untitled', '.txt');
    const name = await prompt({
      title: 'New File',
      description: 'Enter a name for the new file',
      defaultValue: defaultName,
      confirmLabel: 'Create',
    });
    if (name) {
      const fullPath = currentPath ? `${currentPath}/${name}` : name;
      await createFile(fullPath);
    }
  };

  const handleNewFolder = async () => {
    const defaultName = getUniqueName('new-folder');
    const name = await prompt({
      title: 'New Folder',
      description: 'Enter a name for the new folder',
      defaultValue: defaultName,
      confirmLabel: 'Create',
    });
    if (name) {
      const fullPath = currentPath ? `${currentPath}/${name}` : name;
      await createFolder(fullPath);
    }
  };

  const handleRename = async (file: FileInfo) => {
    const existingNames = new Set(files.map((f) => f.name.toLowerCase()));
    const newName = await prompt({
      title: 'Rename',
      description: `Rename "${file.name}" to:`,
      defaultValue: file.name,
      confirmLabel: 'Rename',
    });
    if (newName && newName !== file.name) {
      if (existingNames.has(newName.toLowerCase()) && newName.toLowerCase() !== file.name.toLowerCase()) {
        // Show a second prompt with the error -- re-trigger rename
        await prompt({
          title: 'Name already exists',
          description: `A file or folder named "${newName}" already exists. Choose a different name.`,
          defaultValue: newName,
          confirmLabel: 'Rename',
        }).then(async (retryName) => {
          if (retryName && retryName !== file.name) {
            const parentPath = file.path.substring(0, file.path.lastIndexOf('/'));
            const newPath = parentPath ? `${parentPath}/${retryName}` : retryName;
            await renameFile(file.path, newPath);
          }
        });
        return;
      }

      const parentPath = file.path.substring(0, file.path.lastIndexOf('/'));
      const newPath = parentPath ? `${parentPath}/${newName}` : newName;
      await renameFile(file.path, newPath);
    }
  };

  const handleDelete = async (file: FileInfo) => {
    const confirmed = await confirm({
      title: `Delete "${file.name}"?`,
      description: file.type === 'folder'
        ? 'This folder and all its contents will be permanently deleted.'
        : 'This file will be permanently deleted.',
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (confirmed) {
      await deleteFile(file.path);
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedFiles.length === 0) return;
    const count = selectedFiles.length;
    const confirmed = await confirm({
      title: `Delete ${count} item${count === 1 ? '' : 's'}?`,
      description: 'The selected files and folders will be permanently deleted.',
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (!confirmed) return;
    // Delete sequentially so a single failure doesn't abandon the rest.
    for (const path of selectedFiles) {
      await deleteFile(path);
    }
    setSelectedFiles([]);
  };

  // Remote drives paginate on the server (the store fetches one page at a time),
  // so `files` already holds just the current page. Local synced folders are read
  // entirely in the browser via the File System Access API, so they paginate
  // client-side by slicing the loaded list.
  const isServerPaginated = !isLocalFolder;

  // Remote search + sort are applied by the server, so `files` is already the
  // filtered, sorted page — use it as-is. Local folders are loaded whole in the
  // browser, so we filter and sort them client-side to match.
  const filteredFiles = isServerPaginated
    ? files
    : sortFiles(
        files.filter((file) =>
          file.name.toLowerCase().includes(searchQuery.toLowerCase())
        ),
        filesSortBy,
        filesSortDir,
      );
  const pageCount = isServerPaginated ? filesTotal : filteredFiles.length;
  const totalPages = Math.max(1, Math.ceil(pageCount / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const pageStart = (safePage - 1) * pageSize;
  const pagedFiles = isServerPaginated
    ? filteredFiles
    : filteredFiles.slice(pageStart, pageStart + pageSize);
  // Range shown in the pagination footer ("X–Y of N").
  const rangeStart = pageCount === 0 ? 0 : pageStart + 1;
  const rangeEnd = isServerPaginated
    ? pageStart + pagedFiles.length
    : Math.min(pageStart + pageSize, filteredFiles.length);

  // Fetch a page from the server (remote drives only). Local folders just move
  // the client-side window via setCurrentPage.
  const goToPage = useCallback(
    (page: number) => {
      const clamped = Math.max(1, page);
      setCurrentPage(clamped);
      if (isServerPaginated) {
        fetchFiles(currentPath, {
          limit: pageSize,
          offset: (clamped - 1) * pageSize,
          search: debouncedSearch,
        });
      }
    },
    [isServerPaginated, fetchFiles, currentPath, pageSize, debouncedSearch],
  );

  const changePageSize = (size: number) => {
    setPageSize(size);
    setCurrentPage(1);
    if (isServerPaginated) {
      fetchFiles(currentPath, { limit: size, offset: 0, search: debouncedSearch });
    }
  };

  // Sort a column. setFilesSort updates the persisted preference synchronously,
  // so the follow-up fetch (which reads sort from the store) uses the new order.
  // Local folders re-sort on render, no fetch needed.
  const handleSort = (column: FileSortKey) => {
    setFilesSort(column);
    setCurrentPage(1);
    if (isServerPaginated) {
      fetchFiles(currentPath, { limit: pageSize, offset: 0, search: debouncedSearch });
    }
  };

  // Header cell that sorts its column, with an active-direction arrow.
  const SortHeader = ({ column, label }: { column: FileSortKey; label: string }) => {
    const active = filesSortBy === column;
    return (
      <button
        type="button"
        onClick={() => handleSort(column)}
        className={cn('files-browse-table-sort-btn', active && 'is-active')}
      >
        {label}
        {active &&
          (filesSortDir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
      </button>
    );
  };

  // Navigate into a folder / breadcrumb target: clear any search, reset to page 1
  // and fetch the first server page. Used by the JSX click handlers below.
  const navigateToPath = useCallback(
    (path: string) => {
      setSearchQuery('');
      setDebouncedSearch('');
      lastSearchRef.current = '';
      setCurrentPage(1);
      fetchFiles(path, { limit: pageSizeRef.current, offset: 0, search: '' });
    },
    [fetchFiles],
  );

  // Reset to the first page whenever the search box changes (both modes).
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  // Server-side search: refetch the first page when the debounced term changes.
  // Guarded against the last-fetched term so navigation/mount fetches (which
  // already carry the right search) don't trigger a redundant round-trip.
  useEffect(() => {
    if (!isServerPaginated) return;
    if (debouncedSearch === lastSearchRef.current) return;
    lastSearchRef.current = debouncedSearch;
    setCurrentPage(1);
    fetchFiles(currentPath, { limit: pageSizeRef.current, offset: 0, search: debouncedSearch });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  // After the total shrinks (e.g. deleting the last item on the last page), pull
  // the current page back into range and reload it. Server-paginated only.
  useEffect(() => {
    if (!isServerPaginated) return;
    const maxPage = Math.max(1, Math.ceil(filesTotal / pageSize));
    if (currentPage > maxPage) {
      setCurrentPage(maxPage);
      fetchFiles(currentPath, {
        limit: pageSize,
        offset: (maxPage - 1) * pageSize,
        search: lastSearchRef.current,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filesTotal]);

  const toggleSelectFile = (path: string) => {
    setSelectedFiles((prev) =>
      prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path]
    );
  };

  // Select-all operates on the currently visible page so the header checkbox
  // reflects what the user can actually see.
  const allSelected =
    pagedFiles.length > 0 && pagedFiles.every((f) => selectedFiles.includes(f.path));
  const someSelected = selectedFiles.length > 0 && !allSelected;

  const toggleSelectAll = () => {
    const pagePaths = pagedFiles.map((f) => f.path);
    setSelectedFiles((prev) =>
      allSelected
        ? prev.filter((p) => !pagePaths.includes(p))
        : Array.from(new Set([...prev, ...pagePaths]))
    );
  };

  const formatSize = (bytes?: number) => {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (date?: string) => {
    if (!date) return '—';
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const getFileExtension = (name: string) => {
    const idx = name.lastIndexOf('.');
    return idx >= 0 ? name.slice(idx + 1).toLowerCase() : '';
  };

  const getFileIcon = (file: FileInfo, size = 16) => {
    if (file.type === 'folder') {
      return <Folder size={size} className="text-muted-foreground" />;
    }

    const ext = getFileExtension(file.name);
    const contentType = file.content_type?.toLowerCase() || '';

    if (ext === 'pdf') return <FileText size={size} className="text-red-500" />;
    if (['md', 'markdown'].includes(ext)) return <FileText size={size} className="text-sky-600" />;
    if (['ppt', 'pptx', 'key'].includes(ext)) return <Presentation size={size} className="text-orange-500" />;
    if (['txt', 'doc', 'docx', 'rtf'].includes(ext)) return <FileText size={size} className="text-blue-500" />;
    if (['xls', 'xlsx', 'xlsm', 'xlsb'].includes(ext)) return <FileSpreadsheet size={size} className="text-emerald-700" />;
    if (['csv', 'tsv'].includes(ext)) return <FileSpreadsheet size={size} className="text-emerald-500" />;
    if (['json', 'yaml', 'yml'].includes(ext)) return <FileJson size={size} className="text-amber-500" />;
    if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) return <FileArchive size={size} className="text-orange-500" />;
    if (['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(ext) || contentType.startsWith('video/')) {
      return <FileVideo size={size} className="text-fuchsia-500" />;
    }
    if (['mp3', 'wav', 'ogg', 'flac', 'm4a'].includes(ext) || contentType.startsWith('audio/')) {
      return <FileAudio size={size} className="text-pink-500" />;
    }
    if (
      ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) ||
      contentType.startsWith('image/')
    ) {
      return <FileImage size={size} className="text-violet-500" />;
    }
    if (
      ['js', 'jsx', 'ts', 'tsx', 'py', 'java', 'go', 'rs', 'rb', 'php', 'cs', 'cpp', 'c', 'h', 'sh', 'sql'].includes(ext)
    ) {
      return <FileCode2 size={size} className="text-cyan-500" />;
    }

    return <FileCode size={size} className="text-muted-foreground" />;
  };

  const isPdfFile = (file: FileInfo) =>
    file.type === 'file' && (
      file.name.toLowerCase().endsWith('.pdf') ||
      file.content_type === 'application/pdf'
    );

  const isImageFile = (file: FileInfo) => {
    if (file.type !== 'file') return false;
    const lowerName = file.name.toLowerCase();
    return (
      lowerName.endsWith('.png') ||
      lowerName.endsWith('.jpg') ||
      lowerName.endsWith('.jpeg') ||
      lowerName.endsWith('.gif') ||
      lowerName.endsWith('.webp') ||
      lowerName.endsWith('.svg') ||
      file.content_type?.startsWith('image/') === true
    );
  };

  const isHtmlFile = (file: FileInfo) => {
    if (file.type !== 'file') return false;
    const lowerName = file.name.toLowerCase();
    return (
      lowerName.endsWith('.html') ||
      lowerName.endsWith('.htm') ||
      file.content_type === 'text/html'
    );
  };

  const isMarkdownFile = (file: FileInfo) => {
    if (file.type !== 'file') return false;
    const lowerName = file.name.toLowerCase();
    return (
      lowerName.endsWith('.md') ||
      lowerName.endsWith('.markdown') ||
      lowerName.endsWith('.mdx') ||
      file.content_type === 'text/markdown'
    );
  };

  // Extensions that are reliably plain text. Markdown is detected separately
  // so it can be rendered with ReactMarkdown instead of as raw source.
  const TEXT_EXTENSIONS = new Set([
    'txt', 'log', 'rst', 'tex', 'csv', 'tsv',
    'json', 'jsonc', 'json5', 'ndjson', 'geojson',
    'yaml', 'yml', 'toml', 'ini', 'cfg', 'conf', 'properties', 'env',
    'xml', 'plist', 'svg', 'gql', 'graphql', 'proto',
    'html', 'htm', 'css', 'scss', 'sass', 'less', 'styl',
    'js', 'jsx', 'mjs', 'cjs', 'ts', 'tsx', 'vue', 'svelte', 'astro',
    'py', 'pyi', 'rb', 'go', 'rs', 'java', 'kt', 'kts', 'swift',
    'c', 'h', 'cc', 'cpp', 'hpp', 'cs', 'm', 'mm',
    'php', 'lua', 'r', 'jl', 'dart', 'sql', 'pl', 'pm',
    'sh', 'bash', 'zsh', 'fish', 'ps1', 'bat', 'cmd',
    'patch', 'diff', 'gitignore', 'gitattributes', 'editorconfig',
    'lock', 'in', 'mk',
  ]);

  // Filenames (no extension or special) that we know are text.
  const TEXT_FILENAMES = new Set([
    'dockerfile', 'makefile', 'rakefile', 'gemfile', 'procfile',
    'license', 'readme', 'changelog', 'authors', 'contributors', 'notice',
    '.gitignore', '.gitattributes', '.editorconfig', '.env', '.npmrc', '.nvmrc',
  ]);

  const isTextFile = (file: FileInfo) => {
    if (file.type !== 'file') return false;
    if (isMarkdownFile(file)) return true;
    const lowerName = file.name.toLowerCase();
    if (TEXT_FILENAMES.has(lowerName)) return true;
    const ext = getFileExtension(file.name);
    if (ext && TEXT_EXTENSIONS.has(ext)) return true;
    const ct = file.content_type?.toLowerCase() || '';
    if (ct.startsWith('text/')) return true;
    if (
      ct === 'application/json' ||
      ct === 'application/xml' ||
      ct === 'application/javascript' ||
      ct === 'application/x-yaml' ||
      ct === 'application/x-sh' ||
      ct.endsWith('+json') ||
      ct.endsWith('+xml')
    ) {
      return true;
    }
    return false;
  };

  // Office formats we render via server-side LibreOffice → PDF conversion.
  const OFFICE_PREVIEW_EXTENSIONS = new Set([
    'ppt', 'pptx', 'odp', 'key',
    'doc', 'docx', 'odt', 'rtf',
    'xls', 'xlsx', 'xlsm', 'xlsb', 'ods',
  ]);

  const isOfficeFile = (file: FileInfo) => {
    if (file.type !== 'file') return false;
    return OFFICE_PREVIEW_EXTENSIONS.has(getFileExtension(file.name));
  };

  const officeKindLabel = (file: FileInfo): string => {
    const ext = getFileExtension(file.name);
    if (['doc', 'docx', 'odt', 'rtf'].includes(ext)) return 'Document';
    if (['xls', 'xlsx', 'xlsm', 'xlsb', 'ods'].includes(ext)) return 'Spreadsheet';
    return 'Presentation';
  };

  const openPdfViewer = async (file: FileInfo) => {
    if (!isPdfFile(file)) return;
    setPdfViewerError(null);
    setPdfViewerLoading(true);
    setPdfViewerFileName(file.name);
    setPdfViewerDownloadFile(null);

    if (pdfViewerUrl) {
      URL.revokeObjectURL(pdfViewerUrl);
      setPdfViewerUrl(null);
    }

    try {
      const encodedPath = file.path.split('/').map(encodeURIComponent).join('/');
      const response = await authFetch(
        `/api/files/raw/${encodedPath}?${fileQueryParams}`
      );
      if (!response.ok) {
        throw new Error('Failed to load PDF preview');
      }
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(
        blob.type ? blob : new Blob([blob], { type: 'application/pdf' })
      );
      setPdfViewerUrl(blobUrl);
    } catch (error) {
      setPdfViewerError(error instanceof Error ? error.message : 'Failed to load PDF preview');
    } finally {
      setPdfViewerLoading(false);
    }
  };

  const closePdfViewer = () => {
    setPdfViewerFileName(null);
    setPdfViewerError(null);
    setPdfViewerDownloadFile(null);
    if (pdfViewerUrl) {
      URL.revokeObjectURL(pdfViewerUrl);
    }
    setPdfViewerUrl(null);
    setPdfViewerLoading(false);
  };

  const openOfficePreview = async (file: FileInfo) => {
    if (!isOfficeFile(file)) return;
    setPdfViewerError(null);
    setPdfViewerLoading(true);
    setPdfViewerFileName(`${file.name} (PDF preview)`);
    setPdfViewerDownloadFile(file);

    if (pdfViewerUrl) {
      URL.revokeObjectURL(pdfViewerUrl);
      setPdfViewerUrl(null);
    }

    try {
      const encodedPath = file.path.split('/').map(encodeURIComponent).join('/');
      const response = await authFetch(
        `/api/files/preview/pdf/${encodedPath}?${fileQueryParams}`
      );
      if (!response.ok) {
        throw new Error(`${officeKindLabel(file)} preview unavailable right now`);
      }
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(
        blob.type ? blob : new Blob([blob], { type: 'application/pdf' })
      );
      setPdfViewerUrl(blobUrl);
    } catch (error) {
      setPdfViewerFileName(null);
      setPdfViewerDownloadFile(null);
      setPdfViewerLoading(false);
      // Graceful fallback: download original presentation when conversion is unavailable.
      await downloadFileToDesktop(file);
      return;
    } finally {
      setPdfViewerLoading(false);
    }
  };

  const openImageViewer = async (file: FileInfo) => {
    if (!isImageFile(file)) return;
    setImageViewerError(null);
    setImageViewerLoading(true);
    setImageViewerFileName(file.name);

    if (imageViewerUrl) {
      URL.revokeObjectURL(imageViewerUrl);
      setImageViewerUrl(null);
    }

    try {
      const encodedPath = file.path.split('/').map(encodeURIComponent).join('/');
      const response = await authFetch(
        `/api/files/raw/${encodedPath}?${fileQueryParams}`
      );
      if (!response.ok) {
        throw new Error('Failed to load image preview');
      }
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      setImageViewerUrl(blobUrl);
    } catch (error) {
      setImageViewerError(error instanceof Error ? error.message : 'Failed to load image preview');
    } finally {
      setImageViewerLoading(false);
    }
  };

  const closeImageViewer = () => {
    setImageViewerFileName(null);
    setImageViewerError(null);
    if (imageViewerUrl) {
      URL.revokeObjectURL(imageViewerUrl);
    }
    setImageViewerUrl(null);
    setImageViewerLoading(false);
  };

  const openTextViewer = async (file: FileInfo) => {
    if (!isTextFile(file)) return;
    const mode: 'markdown' | 'code' = isMarkdownFile(file) ? 'markdown' : 'code';
    const html = isHtmlFile(file);
    setTextViewerError(null);
    setTextViewerLoading(true);
    setTextViewerFileName(file.name);
    setTextViewerMode(mode);
    setTextViewerIsHtml(html);
    setHtmlPreview(html); // HTML opens rendered; user can toggle to source
    setTextViewerContent('');

    try {
      const encodedPath = file.path.split('/').map(encodeURIComponent).join('/');
      const response = await authFetch(
        `/api/files/${encodedPath}?${fileQueryParams}`
      );
      if (!response.ok) {
        if (response.status === 415 || response.status === 422) {
          throw new Error('This file is not a UTF-8 text file.');
        }
        throw new Error('Failed to load preview');
      }
      const data = await response.json();
      setTextViewerContent(typeof data.content === 'string' ? data.content : '');
    } catch (error) {
      setTextViewerError(error instanceof Error ? error.message : 'Failed to load preview');
    } finally {
      setTextViewerLoading(false);
    }
  };

  const closeTextViewer = () => {
    setTextViewerFileName(null);
    setTextViewerContent('');
    setTextViewerError(null);
    setTextViewerLoading(false);
    setTextViewerIsHtml(false);
    setHtmlPreview(true);
  };

  const downloadFileToDesktop = async (file: FileInfo) => {
    if (file.type !== 'file') return;
    try {
      const encodedPath = file.path.split('/').map(encodeURIComponent).join('/');
      const response = await authFetch(
        `/api/files/raw/${encodedPath}?${fileQueryParams}`
      );
      if (!response.ok) {
        throw new Error('Failed to download file');
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to download file');
    }
  };

  const downloadFolderToDesktop = async (folder: FileInfo) => {
    if (folder.type !== 'folder') return;
    try {
      const encodedPath = folder.path.split('/').map(encodeURIComponent).join('/');
      const response = await authFetch(
        `/api/files/archive/${encodedPath}?${fileQueryParams}`
      );
      if (!response.ok) {
        let detail = 'Failed to download folder';
        try {
          const data = await response.json();
          if (data?.detail) detail = data.detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${folder.name}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to download folder');
    }
  };

  const handleRefresh = () => {
    if (isLocalFolder && activeSyncedFolder) {
      fetchLocalFiles(activeSyncedFolder.id, currentPath);
    } else {
      refreshFiles();
    }
  };

  const openFileItem = (file: FileInfo) => {
    if (file.type === 'folder') {
      if (isLocalFolder && activeSyncedFolder) {
        fetchLocalFiles(activeSyncedFolder.id, file.path);
      } else {
        navigateToPath(file.path);
      }
    } else if (isOfficeFile(file)) {
      openOfficePreview(file);
    } else if (isImageFile(file)) {
      openImageViewer(file);
    } else if (isPdfFile(file)) {
      openPdfViewer(file);
    } else if (isTextFile(file)) {
      openTextViewer(file);
    } else {
      openFile(file.path);
    }
  };

  const renderFileContextMenu = (file: FileInfo, menuClassName?: string) => {
    const starred = starredItems.some(
      (i) => i.path === file.path && i.workspaceId === workspaceId
    );
    return (
      <div className={cn('files-browse-row-actions', menuClassName)}>
        <button
          type="button"
          title={starred ? 'Remove from starred' : 'Add to starred'}
          onClick={(e) => {
            e.stopPropagation();
            if (starred) {
              unstarItem(file.path, workspaceId);
            } else {
              starItem({
                path: file.path,
                name: file.name,
                type: file.type,
                source: activeSource,
                workspaceId,
              });
            }
          }}
          className={cn(
            'files-browse-row-action-btn files-browse-row-action-star',
            starred && 'is-starred',
          )}
        >
          <Star size={14} className={starred ? 'fill-current' : ''} />
        </button>
        <button
          type="button"
          title={file.type === 'folder' ? 'Download as ZIP' : 'Download'}
          onClick={(e) => {
            e.stopPropagation();
            if (file.type === 'folder') {
              downloadFolderToDesktop(file);
            } else {
              downloadFileToDesktop(file);
            }
          }}
          className="files-browse-row-action-btn files-browse-row-action-download"
        >
          <Download size={14} />
        </button>
        <button
          type="button"
          title="More options"
          onClick={(e) => {
            e.stopPropagation();
            setActiveContextMenu(activeContextMenu === file.path ? null : file.path);
          }}
          className="files-browse-row-action-btn"
        >
          <MoreVertical size={16} />
        </button>
        {activeContextMenu === file.path && (
          <div className="files-browse-row-context-menu">
            {file.type === 'file' && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveContextMenu(null);
                  handleOpenInLab(file);
                }}
                className="files-browse-row-context-item"
              >
                <FlaskConical size={14} />
                Open in Lab
              </button>
            )}
            {isOfficeFile(file) && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveContextMenu(null);
                  openOfficePreview(file);
                }}
                className="files-browse-row-context-item"
              >
                <Eye size={14} />
                Preview {officeKindLabel(file)}
              </button>
            )}
            {isPdfFile(file) && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveContextMenu(null);
                  openPdfViewer(file);
                }}
                className="files-browse-row-context-item"
              >
                <Eye size={14} />
                View PDF
              </button>
            )}
            {isImageFile(file) && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveContextMenu(null);
                  openImageViewer(file);
                }}
                className="files-browse-row-context-item"
              >
                <Eye size={14} />
                View Image
              </button>
            )}
            {isTextFile(file) && !isPdfFile(file) && !isImageFile(file) && !isOfficeFile(file) && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveContextMenu(null);
                  openTextViewer(file);
                }}
                className="files-browse-row-context-item"
              >
                <Eye size={14} />
                {isMarkdownFile(file) ? 'View Markdown' : 'Preview'}
              </button>
            )}
            {starred ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveContextMenu(null);
                  unstarItem(file.path, workspaceId);
                }}
                className="files-browse-row-context-item"
              >
                <Star size={14} />
                Remove from starred
              </button>
            ) : (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveContextMenu(null);
                  starItem({
                    path: file.path,
                    name: file.name,
                    type: file.type,
                    source: activeSource,
                    workspaceId,
                  });
                }}
                className="files-browse-row-context-item"
              >
                <Star size={14} />
                Add to starred
              </button>
            )}
            {file.type === 'file' && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveContextMenu(null);
                  downloadFileToDesktop(file);
                }}
                className="files-browse-row-context-item"
              >
                <Download size={14} />
                Download
              </button>
            )}
            {file.type === 'folder' && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveContextMenu(null);
                  downloadFolderToDesktop(file);
                }}
                className="files-browse-row-context-item"
              >
                <Download size={14} />
                Download as ZIP
              </button>
            )}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setActiveContextMenu(null);
                handleRename(file);
              }}
              className="files-browse-row-context-item"
            >
              Rename
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setActiveContextMenu(null);
                handleDelete(file);
              }}
              className="files-browse-row-context-item files-browse-row-context-item-destructive"
            >
              Delete
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <>
    {promptDialog}
    {confirmDialog}
    <div className="files-browse-root">
      <Header 
        title={driveLabel}
        subtitle={isLocalFolder ? 'Synced from your machine' : undefined} 
      />

      {/* Error banner */}
      {error && (
        <div className="files-browse-error-banner">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="files-browse-error-banner-dismiss"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="files-browse-body">
        {/* Breadcrumb — hidden at drive root on mobile (shell top bar already shows drive name) */}
        {(!isMobile || relativePath) && (
        <div className="files-browse-breadcrumb">
          <button
            type="button"
            onClick={() => {
              if (isLocalFolder && activeSyncedFolder) {
                fetchLocalFiles(activeSyncedFolder.id, '');
              } else {
                navigateToPath('');
              }
            }}
            className={cn(
              'files-browse-breadcrumb-link',
              !relativePath && 'is-current',
            )}
          >
            {driveLabel}
          </button>
          {relativePath && relativePath.split('/').map((part, i, arr) => (
            <span key={i} className="files-browse-breadcrumb-segment">
              <span className="files-browse-breadcrumb-separator">/</span>
              <button
                type="button"
                onClick={() => {
                  const sub = arr.slice(0, i + 1).join('/');
                  if (isLocalFolder && activeSyncedFolder) {
                    fetchLocalFiles(activeSyncedFolder.id, sub);
                  } else {
                    // Send the storage-relative path so the API resolver anchors it
                    // under the drive root (server normalizes a leading drive root).
                    const fullPath = driveRoot ? `${driveRoot}/${sub}` : sub;
                    navigateToPath(fullPath);
                  }
                }}
                className={cn(
                  'files-browse-breadcrumb-link',
                  i === arr.length - 1 && 'is-current',
                )}
              >
                {part}
              </button>
            </span>
          ))}
        </div>
        )}

        {/* Toolbar */}
        <div className="files-browse-toolbar-wrap">
          <FilesMobileToolbar
            isLocalFolder={isLocalFolder}
            loading={loading}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            viewMode={viewMode}
            onViewModeChange={(mode) => {
              setViewMode(mode);
              setToolbarMenuOpen(false);
            }}
            onRefresh={handleRefresh}
            onAddClick={() => setAddSheetOpen(true)}
            menuOpen={toolbarMenuOpen}
            onMenuToggle={(e) => {
              e.stopPropagation();
              setToolbarMenuOpen((open) => !open);
            }}
          />
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileInputChange}
            className="files-browse-hidden-input"
          />

          {/* Desktop toolbar */}
          <div className="files-browse-toolbar-desktop">
            <div className="files-browse-toolbar-actions">
              {!isLocalFolder && (
                <>
                  <button
                    type="button"
                    onClick={handleNewFile}
                    className="files-browse-toolbar-btn files-browse-toolbar-btn-primary"
                  >
                    <FileCode size={16} />
                    New File
                  </button>
                  <button
                    type="button"
                    onClick={handleNewFolder}
                    className="files-browse-toolbar-btn files-browse-toolbar-btn-outline"
                  >
                    <FolderPlus size={16} />
                    New Folder
                  </button>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="files-browse-toolbar-btn files-browse-toolbar-btn-outline"
                  >
                    <Upload size={16} />
                    Upload
                  </button>
                </>
              )}
              <button
                type="button"
                onClick={handleRefresh}
                disabled={loading}
                className={cn(
                  'files-browse-toolbar-btn files-browse-toolbar-btn-outline',
                  loading && 'is-disabled',
                )}
              >
                <RefreshCw
                  size={16}
                  className={cn('files-browse-toolbar-btn-icon', loading && 'is-spinning')}
                />
                Refresh
              </button>

              <div className="files-browse-toolbar-view-toggle">
                <button
                  type="button"
                  onClick={() => setViewMode('list')}
                  className={cn(
                    'files-browse-toolbar-view-btn',
                    viewMode === 'list' && 'is-active',
                  )}
                  aria-label="List view"
                >
                  <List size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('grid')}
                  className={cn(
                    'files-browse-toolbar-view-btn',
                    viewMode === 'grid' && 'is-active',
                  )}
                  aria-label="Grid view"
                >
                  <Grid size={16} />
                </button>
              </div>
            </div>

            <div className="files-browse-toolbar-search-wrap">
              <div className="files-browse-toolbar-search">
                <Search size={16} className="files-browse-toolbar-search-icon" />
                <input
                  type="text"
                  placeholder="Search files..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="files-browse-toolbar-search-input"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Selection action bar (list view, desktop only — mobile has no row checkboxes) */}
        {viewMode === 'list' && !isLocalFolder && !isMobile && selectedFiles.length > 0 && (
          <div className="files-browse-selection-bar">
            <span className="files-browse-selection-count">
              {selectedFiles.length} selected
            </span>
            <div className="files-browse-selection-actions">
              <button
                type="button"
                onClick={() => setSelectedFiles([])}
                className="files-browse-selection-btn"
              >
                Clear
              </button>
              <button
                type="button"
                onClick={handleDeleteSelected}
                className="files-browse-selection-btn files-browse-selection-btn-destructive"
              >
                <Trash2 size={14} />
                Delete
              </button>
            </div>
          </div>
        )}

        {/* Content */}
        <div 
          className={cn(
            'files-browse-content',
            isDragging && 'is-dragging',
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {/* Drag overlay */}
          {isDragging && (
            <div className="files-browse-drag-overlay">
              <div className="files-browse-drag-panel">
                <Upload size={48} className="files-browse-drag-icon" />
                <p className="files-browse-drag-title">Drop files here to upload</p>
                <p className="files-browse-drag-subtitle">Files and folders will be uploaded to the current folder</p>
              </div>
            </div>
          )}

          {uploadProgress && (
            <div className="files-browse-upload-toast">
              <div className="files-browse-upload-header">
                <div className="files-browse-upload-header-inner">
                  <Upload
                    size={16}
                    className={cn(
                      'files-browse-upload-icon',
                      uploadProgress.active && 'is-active',
                    )}
                  />
                  <p className="files-browse-upload-title">
                    {uploadProgress.active
                      ? `Uploading ${uploadProgress.completed + 1} of ${uploadProgress.total}`
                      : uploadProgress.failed > 0
                        ? `Uploaded ${uploadProgress.completed} of ${uploadProgress.total} (${uploadProgress.failed} failed)`
                        : `Uploaded ${uploadProgress.completed} file${uploadProgress.completed === 1 ? '' : 's'}`}
                  </p>
                </div>
              </div>
              <div className="files-browse-upload-body">
                <div className="files-browse-upload-track">
                  <div
                    className="files-browse-upload-fill"
                    style={{
                      width: `${uploadProgress.total === 0 ? 0 : ((uploadProgress.completed + uploadProgress.failed) / uploadProgress.total) * 100}%`,
                    }}
                  />
                </div>
                {uploadProgress.currentName && (
                  <p className="files-browse-upload-filename" title={uploadProgress.currentName}>
                    {uploadProgress.currentName}
                  </p>
                )}
                {uploadProgress.active && (
                  <p className="files-browse-upload-hint">
                    Please keep this page open until the upload finishes.
                  </p>
                )}
              </div>
            </div>
          )}

          {error && (
            <div className="files-browse-error-inline">
              {error}
            </div>
          )}

          {loading && filteredFiles.length === 0 ? (
            <div className="files-browse-empty">
              <div className="files-browse-empty-icon-wrap">
                <RefreshCw size={32} className="files-browse-empty-icon files-browse-toolbar-btn-icon is-spinning" />
              </div>
              <h3 className="files-browse-empty-title">Loading files…</h3>
            </div>
          ) : filteredFiles.length === 0 ? (
            <div className="files-browse-empty">
              <div className="files-browse-empty-icon-wrap">
                <Folder size={32} className="files-browse-empty-icon" />
              </div>
              <h3 className="files-browse-empty-title">
                {searchQuery ? 'No files found' : isLocalFolder ? 'Folder is empty' : 'No files yet'}
              </h3>
              <p className="files-browse-empty-text">
                {searchQuery 
                  ? 'Try a different search term' 
                  : isLocalFolder 
                    ? 'This folder has no files or subfolders'
                    : 'Create a file or folder to get started'}
              </p>
              {!searchQuery && !isLocalFolder && (
                <div className="files-browse-empty-actions">
                  <div className="files-browse-empty-btn-row">
                    <button
                      type="button"
                      onClick={handleNewFile}
                      className="files-browse-empty-btn files-browse-empty-btn-primary"
                    >
                      <FileCode size={14} />
                      New File
                    </button>
                    <button
                      type="button"
                      onClick={handleNewFolder}
                      className="files-browse-empty-btn files-browse-empty-btn-outline"
                    >
                      <FolderPlus size={14} />
                      New Folder
                    </button>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="files-browse-empty-btn files-browse-empty-btn-outline"
                    >
                      <Upload size={14} />
                      Upload Files
                    </button>
                  </div>
                  <p className="files-browse-empty-hint">
                    Or drag and drop files anywhere on this page
                  </p>
                </div>
              )}
            </div>
          ) : viewMode === 'list' ? (
            <>
            {/* Desktop list — table */}
            <table className="files-browse-table">
              <thead>
                <tr className="files-browse-table-head-row">
                  {!isLocalFolder && (
                    <th className="files-browse-table-head-cell files-browse-table-head-cell-checkbox">
                      <input
                        type="checkbox"
                        aria-label="Select all"
                        checked={allSelected}
                        ref={(el) => {
                          if (el) el.indeterminate = someSelected;
                        }}
                        onChange={toggleSelectAll}
                        className="files-browse-table-checkbox"
                      />
                    </th>
                  )}
                  <th className="files-browse-table-head-cell">
                    <SortHeader column="name" label="Name" />
                  </th>
                  <th className="files-browse-table-head-cell">
                    <SortHeader column="size" label="Size" />
                  </th>
                  <th className="files-browse-table-head-cell">
                    <SortHeader column="modified" label="Modified" />
                  </th>
                  <th className="files-browse-table-head-cell files-browse-table-head-cell-actions"></th>
                </tr>
              </thead>
              <tbody>
                {pagedFiles.map((file) => (
                  <tr
                    key={file.path}
                    draggable={!isLocalFolder}
                    onDragStart={(e) => handleRowDragStart(e, file)}
                    onDragOver={file.type === 'folder' && !isLocalFolder ? (e) => handleFolderDragOver(e, file) : undefined}
                    onDragLeave={file.type === 'folder' && !isLocalFolder ? (e) => handleFolderDragLeave(e, file) : undefined}
                    onDrop={file.type === 'folder' && !isLocalFolder ? (e) => handleFolderDrop(e, file) : undefined}
                    className={cn(
                      'files-browse-table-row',
                      selectedFiles.includes(file.path) && 'is-selected',
                      dropTargetPath === file.path && 'is-drop-target',
                    )}
                  >
                    {!isLocalFolder && (
                      <td className="files-browse-table-cell files-browse-table-cell-checkbox">
                        <input
                          type="checkbox"
                          aria-label={`Select ${file.name}`}
                          checked={selectedFiles.includes(file.path)}
                          onChange={() => toggleSelectFile(file.path)}
                          className="files-browse-table-checkbox"
                        />
                      </td>
                    )}
                    <td className="files-browse-table-cell">
                      <button
                        type="button"
                        onClick={() => openFileItem(file)}
                        className="files-browse-table-name-btn"
                      >
                        <span className="files-browse-table-name-icon">{getFileIcon(file, 16)}</span>
                        <span className="files-browse-table-name-text">{file.name}</span>
                      </button>
                    </td>
                    <td className="files-browse-table-cell files-browse-table-cell-meta">
                      {file.type === 'folder' ? '—' : formatSize(file.size)}
                    </td>
                    <td className="files-browse-table-cell files-browse-table-cell-meta">
                      {formatDate(file.modified)}
                    </td>
                    <td className="files-browse-table-cell">
                      {renderFileContextMenu(file)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <ul className="files-mobile-list" aria-label="Files">
              {pagedFiles.map((file) => (
                <FilesMobileRow
                  key={file.path}
                  file={file}
                  isDropTarget={dropTargetPath === file.path}
                  icon={getFileIcon(file, 20)}
                  sizeLabel={formatSize(file.size)}
                  dateLabel={formatDate(file.modified)}
                  onOpen={() => openFileItem(file)}
                  onDragStart={!isLocalFolder ? (e) => handleRowDragStart(e, file) : undefined}
                  onDragOver={
                    file.type === 'folder' && !isLocalFolder
                      ? (e) => handleFolderDragOver(e, file)
                      : undefined
                  }
                  onDragLeave={
                    file.type === 'folder' && !isLocalFolder
                      ? (e) => handleFolderDragLeave(e, file)
                      : undefined
                  }
                  onDrop={
                    file.type === 'folder' && !isLocalFolder
                      ? (e) => handleFolderDrop(e, file)
                      : undefined
                  }
                  actions={renderFileContextMenu(file)}
                />
              ))}
            </ul>
            </>
          ) : (
            /* Grid view */
            <div className="files-browse-grid">
              {pagedFiles.map((file) => (
                <div
                  key={file.path}
                  draggable={!isLocalFolder}
                  onDragStart={(e) => handleRowDragStart(e, file)}
                  onDragOver={file.type === 'folder' && !isLocalFolder ? (e) => handleFolderDragOver(e, file) : undefined}
                  onDragLeave={file.type === 'folder' && !isLocalFolder ? (e) => handleFolderDragLeave(e, file) : undefined}
                  onDrop={file.type === 'folder' && !isLocalFolder ? (e) => handleFolderDrop(e, file) : undefined}
                  className={cn(
                    'files-browse-grid-item',
                    dropTargetPath === file.path && 'is-drop-target',
                  )}
                >
                  <button
                    type="button"
                    onClick={() => openFileItem(file)}
                    className="files-browse-grid-card"
                  >
                    {getFileIcon(file, 40)}
                    <span className="files-browse-grid-name">{file.name}</span>
                  </button>
                  {(() => {
                    const starred = starredItems.some(
                      (i) => i.path === file.path && i.workspaceId === workspaceId
                    );
                    return (
                      <button
                        type="button"
                        title={starred ? 'Remove from starred' : 'Add to starred'}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (starred) {
                            unstarItem(file.path, workspaceId);
                          } else {
                            starItem({
                              path: file.path,
                              name: file.name,
                              type: file.type,
                              source: activeSource,
                              workspaceId,
                            });
                          }
                        }}
                        className={cn(
                          'files-browse-grid-star-btn',
                          starred && 'is-starred',
                        )}
                      >
                        <Star size={13} className={starred ? 'fill-current' : ''} />
                      </button>
                    );
                  })()}
                  <button
                    type="button"
                    title={file.type === 'folder' ? 'Download as ZIP' : 'Download'}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (file.type === 'folder') {
                        downloadFolderToDesktop(file);
                      } else {
                        downloadFileToDesktop(file);
                      }
                    }}
                    className="files-browse-grid-download-btn"
                  >
                    <Download size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pagination bar */}
        {pageCount > 0 && (
          <div className={cn(
            'files-browse-pagination',
            isMobile && 'files-browse-pagination-compact',
          )}>
            <div className="files-browse-pagination-page-size">
              <span>Rows per page</span>
              <select
                value={pageSize}
                onChange={(e) => changePageSize(Number(e.target.value))}
                className="files-browse-pagination-select"
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </div>
            <div className="files-browse-pagination-controls">
              <span className="files-browse-pagination-range">
                {`${rangeStart}–${rangeEnd} of ${pageCount}`}
              </span>
              <div className="files-browse-pagination-nav">
                <button
                  type="button"
                  onClick={() => goToPage(safePage - 1)}
                  disabled={loading || safePage <= 1}
                  className="files-browse-pagination-nav-btn"
                >
                  Previous
                </button>
                {!isMobile && (
                  <span className="files-browse-pagination-page-info">
                    {`Page ${safePage} of ${totalPages}`}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => goToPage(safePage + 1)}
                  disabled={loading || safePage >= totalPages}
                  className="files-browse-pagination-nav-btn"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

    </div>

      <FilesAddSheet
        open={addSheetOpen}
        onClose={() => setAddSheetOpen(false)}
        onNewFile={() => void handleNewFile()}
        onNewFolder={() => void handleNewFolder()}
        onUpload={() => fileInputRef.current?.click()}
      />

      {/* PDF Viewer modal — rendered outside the page container to avoid stacking-context traps */}
      {pdfViewerFileName && (
        <div className="fixed inset-0 z-[200] bg-black/60 p-4 backdrop-blur-sm">
          <div className="flex h-full flex-col overflow-hidden rounded-xl border bg-background shadow-2xl">
            <div className="flex items-center justify-between border-b px-4 py-2">
              <div className="truncate text-sm font-medium">{pdfViewerFileName}</div>
              <div className="flex items-center gap-2">
                {pdfViewerDownloadFile && (
                  <button
                    onClick={() => downloadFileToDesktop(pdfViewerDownloadFile)}
                    className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs hover:bg-muted"
                  >
                    <Download size={12} />
                    Download original
                  </button>
                )}
                <button
                  onClick={closePdfViewer}
                  className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
                  aria-label="Close PDF viewer"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            <div className="relative flex-1 bg-muted/20">
              {pdfViewerLoading && (
                <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
                  Loading PDF preview...
                </div>
              )}
              {pdfViewerError && !pdfViewerLoading && (
                <div className="absolute inset-0 flex items-center justify-center p-6 text-sm text-destructive">
                  {pdfViewerError}
                </div>
              )}
              {pdfViewerUrl && !pdfViewerLoading && !pdfViewerError && (
                <PdfViewer src={pdfViewerUrl} className="h-full w-full" />
              )}
            </div>
          </div>
        </div>
      )}
      {imageViewerFileName && (
        <div className="fixed inset-0 z-[200] bg-black/60 p-4 backdrop-blur-sm">
          <div className="flex h-full flex-col overflow-hidden rounded-xl border bg-background shadow-2xl">
            <div className="flex items-center justify-between border-b px-4 py-2">
              <div className="truncate text-sm font-medium">{imageViewerFileName}</div>
              <button
                onClick={closeImageViewer}
                className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
                aria-label="Close image viewer"
              >
                <X size={16} />
              </button>
            </div>
            <div className="relative flex-1 bg-black/40">
              {imageViewerLoading && (
                <div className="absolute inset-0 flex items-center justify-center text-sm text-white/80">
                  Loading image preview...
                </div>
              )}
              {imageViewerError && !imageViewerLoading && (
                <div className="absolute inset-0 flex items-center justify-center p-6 text-sm text-destructive">
                  {imageViewerError}
                </div>
              )}
              {imageViewerUrl && !imageViewerLoading && !imageViewerError && (
                <div className="flex h-full w-full items-center justify-center p-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={imageViewerUrl}
                    alt={imageViewerFileName}
                    className="max-h-full max-w-full object-contain"
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      {textViewerFileName && (
        <div className="fixed inset-0 z-[200] bg-black/60 p-4 backdrop-blur-sm">
          <div className="flex h-full flex-col overflow-hidden rounded-xl border bg-background shadow-2xl">
            <div className="flex items-center justify-between border-b px-4 py-2">
              <div className="flex min-w-0 items-center gap-2">
                {textViewerIsHtml && (
                  <div className="flex items-center rounded-md border">
                    <button
                      onClick={() => setHtmlPreview(true)}
                      title="Preview"
                      aria-label="Preview rendered HTML"
                      className={cn(
                        'flex h-7 w-7 items-center justify-center rounded-l-md',
                        htmlPreview ? 'bg-muted' : 'hover:bg-muted/50'
                      )}
                    >
                      <Eye size={14} />
                    </button>
                    <button
                      onClick={() => setHtmlPreview(false)}
                      title="View source"
                      aria-label="View HTML source"
                      className={cn(
                        'flex h-7 w-7 items-center justify-center rounded-r-md border-l',
                        !htmlPreview ? 'bg-muted' : 'hover:bg-muted/50'
                      )}
                    >
                      <Code size={14} />
                    </button>
                  </div>
                )}
                <div className="truncate text-sm font-medium">{textViewerFileName}</div>
              </div>
              <button
                onClick={closeTextViewer}
                className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
                aria-label="Close text viewer"
              >
                <X size={16} />
              </button>
            </div>
            <div className="relative flex-1 overflow-auto bg-background">
              {textViewerLoading && (
                <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
                  Loading preview...
                </div>
              )}
              {textViewerError && !textViewerLoading && (
                <div className="absolute inset-0 flex items-center justify-center p-6 text-sm text-destructive">
                  {textViewerError}
                </div>
              )}
              {!textViewerLoading && !textViewerError && textViewerIsHtml && htmlPreview && (
                <iframe
                  title={textViewerFileName ?? 'HTML preview'}
                  srcDoc={textViewerContent}
                  sandbox="allow-scripts allow-popups allow-forms allow-modals"
                  className="h-full w-full border-0 bg-white"
                />
              )}
              {!textViewerLoading && !textViewerError && textViewerIsHtml && !htmlPreview && (
                <pre className="m-0 h-full overflow-auto whitespace-pre p-4 font-mono text-xs leading-relaxed text-foreground">
                  {textViewerContent}
                </pre>
              )}
              {!textViewerLoading && !textViewerError && !textViewerIsHtml && textViewerMode === 'markdown' && (
                <div className="prose prose-sm max-w-none p-6 dark:prose-invert">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {textViewerContent}
                  </ReactMarkdown>
                </div>
              )}
              {!textViewerLoading && !textViewerError && !textViewerIsHtml && textViewerMode === 'code' && (
                <pre className="m-0 h-full overflow-auto whitespace-pre p-4 font-mono text-xs leading-relaxed text-foreground">
                  {textViewerContent}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
