from pytest import fixture


@fixture
def test_configuration():
    return """
workspace_id: "1234567890"
storage_name: "test"
github_repository: "test"
github_project_id: 1234567890
triple_store_path: "test"
api_title: "test"
api_description: "test"
logo_path: "test"
favicon_path: "test"
space_name: "test"
cors_origins:
  - "http://localhost:9879"

services:
    object_storage: &object_storage_service
      object_storage_adapter:
        adapter: "fs"
        config:
          base_path: "test"
          test: "{{ secret.OXIGRAPH_URL }}"

    triple_store:
      ontology_adapter:
        adapter: "object_storage"
        config:
          triples_prefix: "test"
          object_storage_service: *object_storage_service

        
    vector_store:
      vector_store_adapter:
        adapter: "qdrant"
        config: {}
        
    secret:
      secret_adapters:
        - adapter: "dotenv"
          config: {}
"""
