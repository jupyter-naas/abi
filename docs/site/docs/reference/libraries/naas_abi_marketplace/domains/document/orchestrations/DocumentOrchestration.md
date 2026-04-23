# DocumentOrchestration

## What it is
- A Dagster-based orchestration builder for the **document** domain.
- Dynamically creates Dagster **jobs** and **sensors** based on `ABIModule` configuration:
  - File ingestion pipelines (one job+sensor per configured input path)
  - Optional format-to-markdown pipelines (PDF/DOCX/PPTX)

## Public API
### `class DocumentOrchestration(DagsterOrchestration)`
- **`@classmethod New() -> DocumentOrchestration`**
  - Builds and returns a `DocumentOrchestration` instance containing a `dagster.Definitions` object with:
    - `jobs`: generated Dagster jobs
    - `sensors`: generated Dagster sensors
    - `assets`: empty
    - `schedules`: empty

> Module-level helpers exist (`_build_*_job_sensor`) but are internal (prefixed with `_`) and not part of the public API.

## Configuration/Dependencies
### Dependencies
- `dagster` (imported as `dg`)
- `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`
- `naas_abi_marketplace.domains.document.ABIModule`
- `naas_abi_marketplace.domains.document.FileIngestionConfiguration`
- Pipelines are imported lazily inside ops:
  - `FilesIngestionPipeline`
  - `PdfToMarkdownPipeline`
  - `DocxToMarkdownPipeline`
  - `PptxToMarkdownPipeline`

### Configuration inputs (via `ABIModule.get_instance().configuration`)
- `file_ingestion_pipelines`: iterable of `FileIngestionConfiguration` used to create ingestion jobs/sensors.
  - Each config is used to pass:
    - `input_path`, `output_path`, `graph_name`, `recursive`
- `pdftomarkdown_enabled`: if truthy, adds a PDF-to-Markdown job+sensor.
- `docxtomarkdown_enabled`: if present and truthy (defaults to `True` if missing), adds a DOCX-to-Markdown job+sensor.
- `pptxtomarkdown_enabled`: if present and truthy (defaults to `True` if missing), adds a PPTX-to-Markdown job+sensor.

### Generated Dagster objects
- Each job is a single-op graph converted to a job.
- Each sensor:
  - is tied to its job
  - uses `minimum_interval_seconds=60`
  - currently always yields `[dg.RunRequest(run_key=None)]`

## Usage
```python
from naas_abi_marketplace.domains.document.orchestrations.DocumentOrchestration import (
    DocumentOrchestration,
)

# Build Dagster Definitions (jobs + sensors) from ABIModule configuration
orch = DocumentOrchestration.New()

# Access underlying dagster Definitions if needed
defs = orch.definitions  # provided by DagsterOrchestration base (implementation-dependent)
```

## Caveats
- Sensors do **not** implement file-change detection; they always emit a `RunRequest` every time they are evaluated (subject to `minimum_interval_seconds=60`).
- Job/op names for file ingestion are derived from `input_path` and sanitized to alphanumeric/underscore; different paths could still collide after sanitization.
