from src.core.modules.ontology.workflows.SearchLinkedInPagePipeline import SearchLinkedInPageWorkflow, SearchLinkedInPageWorkflowParameters, SearchLinkedInPageConfigurationWorkflow
from src import services

triple_store = services.triple_store_service

search_linkedin_page_workflow = SearchLinkedInPageWorkflow(SearchLinkedInPageConfigurationWorkflow(triple_store))

search_label = "florent-ravenel/"
results = search_linkedin_page_workflow.search_linkedin(SearchLinkedInPageWorkflowParameters(search_label=search_label))

print(results)





