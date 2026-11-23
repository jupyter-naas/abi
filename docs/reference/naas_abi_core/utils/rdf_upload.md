# rdf_upload

## What it is
Parses an uploaded RDF document as data. `parse_upload` runs rdflib in a child Python process (`python -m naas_abi_core.utils.rdf_upload <format>`) that:
- refuses a JSON-LD document naming a context or an import by URL, before rdflib sees it (only embedded contexts are read);
- cannot open network connections (an audit hook refuses them);
- is killed when it runs longer than `timeout`;
- may use 2 GiB of address space at most (`RLIMIT_AS`, where the platform supports it).

The child hands back at most `MAX_TRIPLES` (1,000,000) triples and `MAX_OUTPUT_BYTES` (256 MiB) of N-Triples, refusing larger graphs with `TOO_LARGE`, so what the parent buffers and parses again is bounded too (both overridable per call).

At most `MAX_CONCURRENT_PARSES` (4) children run at once; a further call waits for a slot within its own timeout.

The child returns the triples as N-Triples, which the caller reads in linear time. Call it off the event loop (`asyncio.to_thread`).

## Public API
- `parse_upload(content: bytes, fmt: str, *, timeout: float = 60.0) -> rdflib.Graph`
- `FORMATS`: `turtle`, `xml`, `nt`, `n3`, `json-ld`.
- `format_for_filename(filename) -> str`: the format of an upload from its file name (`.ttl`, `.owl`/`.rdf`/`.xml`, `.nt`, `.n3`, `.jsonld`/`.json`), Turtle by default.
- `refuse_remote_documents(document)`: the JSON-LD check, on a decoded document.
- `RdfUploadError(ValueError)`: refused or unparsable upload. Its message is one of the fixed constants (`EMBEDDED_CONTEXTS_ONLY`, `NOT_JSON_LD`, `UNSUPPORTED_FORMAT`, `NOT_PARSED`, `TOO_SLOW`), safe to show to a user.

## Usage
```python
import asyncio
from naas_abi_core.utils import rdf_upload

async def count_triples(content: bytes) -> int:
    graph = await asyncio.to_thread(rdf_upload.parse_upload, content, "turtle", timeout=60)
    return len(graph)
```

## Caveats
- Each call starts a Python process (a fraction of a second); it is meant for uploads, not hot paths.
- Cap the upload's size before calling: the child holds the whole document in memory.
