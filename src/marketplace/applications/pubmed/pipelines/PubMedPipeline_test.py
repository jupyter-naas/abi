from src.marketplace.applications.pubmed.pipelines.PubMedPipeline import PubMedPipeline, PubMedPipelineConfiguration, PubMedPipelineParameters

def test_pubmed_pipeline():
    pipeline = PubMedPipeline(PubMedPipelineConfiguration())
    results = pipeline.run(PubMedPipelineParameters(query="rheumatoid arthritis"))
    assert len(results) > 0