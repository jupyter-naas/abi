### PubMed application module

This module provides an application-layer integration with PubMed (NCBI E-utilities) to search biomedical articles, transform the results into a knowledge graph aligned to the project's ontology, and expose the capability as a pipeline and as an agent tool.

#### What it does
- **Search PubMed by query and date range** with adaptive paging and window splitting to respect the 9,999 record cap.
- **Return results as RDF** and serialize them to Turtle (TTL) via the shared `Graph` API.
- **Filter for downloadable papers** (PubMed Central PDFs) when desired.
- **Respect rate limits** and use a filesystem cache for resilience and speed.
- **Model results with an ontology** (`ontologies/PubMed.ttl`) aligned with BFO, including classes such as `PubMedPaperSummary`, `Journal`, and `JournalIssue` and properties like `pubmedIdentifier`, `title`, `doi`, `pmcid`, `url`, and `downloadUrl`.

#### Module structure
- `integrations/PubMedAPI.py`: Integration with NCBI E-utilities (ESearch/ESummary). Handles rate limiting, paging, summary building, and caching.
- `pipelines/PubMedPipeline.py`: Pipeline that orchestrates the integration, builds the RDF graph, and exposes a tool interface.
- `agents/PubMedAgent.py`: Agent wiring that registers the PubMed search as a tool and instructs the agent to render results as Markdown tables.
- `ontologies/PubMed.ttl`: Ontology module for PubMed summaries aligned to BFO.
- `orchestrations/definitions.py`: Dagster definitions placeholder (no jobs/sensors/assets yet).
- `reasoners/`: Placeholder for future reasoning components.

#### Key capabilities
- **Parameters** (pipeline/tool):
  - `query` (str): PubMed query string.
  - `start_date` (str): Inclusive start date (e.g., `YYYY-MM-DD` or `YYYY/MM/DD`).
  - `end_date` (str, optional): Inclusive end date (defaults to today).
  - `sort` (str): One of `pub_date`, `Author`, `JournalName`, or `relevance` (default).
  - `downloadable_only` (bool): If true, only include results with a PubMed Central `downloadUrl`.
  - `max_results` (int): Cap on total results returned.

#### Usage

- Programmatic (pipeline)
  ```python
  from src.marketplace.applications.pubmed.pipelines.PubMedPipeline import (
      PubMedPipeline, PubMedPipelineConfiguration, PubMedPipelineParameters,
  )

  pipeline = PubMedPipeline(PubMedPipelineConfiguration())
  graph = pipeline.run(
      PubMedPipelineParameters(
          query="rheumatoid arthritis",
          start_date="2023-01-01",
          end_date="2023-12-31",
          sort="relevance",
          downloadable_only=True,
          max_results=100,
      )
  )

  turtle = graph.serialize(format="turtle")
  print(turtle)
  ```

- As an Agent tool
  - The agent registers a tool named `search_downloadable_pubmed_papers` with the same parameters as above and returns the graph serialized as Turtle.
  - The agent system prompt instructs rendering results as a Markdown table.

- From the command line
  ```bash
  # From the project root
  python src/marketplace/applications/PubMed/pipelines/PubMedPipeline.py \
    --query "rheumatoid arthritis" \
    --start-date "2023-01-01" \
    --end-date "2023-12-31"
  # Outputs pubmed_output.ttl in the working directory
  ```

#### Configuration and limits
- API base: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`
- Optional API key is supported via `PubMedAPIConfiguration(api_key=...)` to raise rate limits. The pipeline uses default configuration; pass a custom configuration if you instantiate the integration directly.
- Rate limits: default 3 calls/second per configured window; additional internal batching and caching reduce load.

#### Notes
- Output graph uses IRIs derived from PubMed IDs under the ontology namespace; this ensures stable identifiers across runs.
- The `as_api` method is currently a placeholder; HTTP endpoints are not exposed yet.
- Tests and Dagster assets are minimal placeholders; extend as needed for your workflows.


