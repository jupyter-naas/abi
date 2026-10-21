# files__schema

## What it is
Domain-level schema and error definitions for a file service API. It provides:
- Typed data containers (immutable `dataclass`es) for file metadata, content, listings, and previews.
- A small hierarchy of domain exceptions for common file-related failure cases.

## Public API

### Exceptions
- `FilesDomainError(Exception)`: Base exception for all file domain errors in this module.
- `InvalidPathError(FilesDomainError)`: Invalid path provided.
- `AlreadyExistsError(FilesDomainError)`: Target already exists.
- `NotFoundError(FilesDomainError)`: Target does not exist.
- `IsDirectoryError(FilesDomainError)`: Operation attempted on a directory where a file was expected.
- `NotTextError(FilesDomainError)`: Content is not text when text was expected.
- `UnsupportedPreviewError(FilesDomainError)`: Preview type/format not supported.
- `PreviewUnavailableError(FilesDomainError)`: Preview not available.
- `PreviewConversionError(FilesDomainError)`: Preview conversion failed.
- `UploadTooLargeError(FilesDomainError)`: Upload exceeds maximum size.
  - `__init__(max_size_bytes: int)`: Stores `max_size_bytes` and sets message: `"File too large. Max size is {max_size_bytes // (1024 * 1024)}MB"`.

### Data classes (immutable)
- `FileInfoData`
  - Purpose: File metadata.
  - Fields:
    - `name: str`
    - `path: str`
    - `type: str`
    - `size: int | None = None`
    - `modified: datetime | None = None`
    - `content_type: str | None = None`

- `FileContentData`
  - Purpose: Text file content payload.
  - Fields:
    - `path: str`
    - `content: str`
    - `content_type: str`

- `FileListResponseData`
  - Purpose: Listing response containing multiple `FileInfoData`.
  - Fields:
    - `files: list[FileInfoData]`
    - `path: str`

- `RawFileData`
  - Purpose: Raw binary file payload suitable for download/streaming.
  - Fields:
    - `content: bytes`
    - `media_type: str`
    - `filename: str`

- `PdfPreviewData`
  - Purpose: PDF preview payload.
  - Fields:
    - `content: bytes`
    - `filename: str`

## Configuration/Dependencies
- Standard library only:
  - `dataclasses.dataclass`
  - `datetime.datetime`
- Uses `from __future__ import annotations` to allow forward references and modern type hint syntax.

## Usage
```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    FileInfoData,
    FileListResponseData,
    UploadTooLargeError,
)

info = FileInfoData(
    name="report.txt",
    path="/reports/report.txt",
    type="file",
    size=1234,
    modified=datetime.utcnow(),
    content_type="text/plain",
)

listing = FileListResponseData(files=[info], path="/reports")

try:
    raise UploadTooLargeError(max_size_bytes=10 * 1024 * 1024)
except UploadTooLargeError as e:
    print(e.max_size_bytes)  # 10485760
    print(str(e))            # "File too large. Max size is 10MB"
```

## Caveats
- All data classes are `frozen=True` (immutable); you must create new instances instead of mutating fields.
- `UploadTooLargeError` message reports size in whole MB via integer division (`//`), which truncates partial MB.
