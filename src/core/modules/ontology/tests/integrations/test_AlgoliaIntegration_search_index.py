from src import secret
from src.core.modules.ontology.integrations.AlgoliaIntegration import (
    AlgoliaIntegration,
    AlgoliaIntegrationConfiguration,
)
import asyncio

algolia_config = AlgoliaIntegrationConfiguration(
    app_id=secret.get("ALGOLIA_APPLICATION_ID"), api_key=secret.get("ALGOLIA_API_KEY")
)

algolia_integration = AlgoliaIntegration(algolia_config)

index_name = "workspace-search"
query = "Finance"
hits_per_page = 1
filters = "type:ontology AND category:class"

results = asyncio.run(
    algolia_integration.search(
        index_name=index_name, query=query, hits_per_page=hits_per_page, filters=filters
    )
)
print(results)

for r in results:
    print(r[1][0])
