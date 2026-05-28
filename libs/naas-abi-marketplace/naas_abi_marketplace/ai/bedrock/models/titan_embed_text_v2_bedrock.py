from langchain_aws import BedrockEmbeddings
from naas_abi_core.models.Model import (
    CanonicalModelId,
    EmbeddingModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.bedrock import ABIModule


class TitanEmbedTextV2BedrockModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.TITAN_EMBED_TEXT_V2
    MODEL_ID = "amazon.titan-embed-text-v2:0"
    PROVIDER = ModelProvider.BEDROCK

    _cfg = ABIModule.get_instance().configuration

    model: EmbeddingModel = EmbeddingModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=BedrockEmbeddings(
            model_id=MODEL_ID,
            region_name=_cfg.region_name,
            aws_access_key_id=_cfg.aws_access_key_id,
            aws_secret_access_key=_cfg.aws_secret_access_key,
            aws_session_token=_cfg.aws_session_token,
        ),
    )


# Back-compat with the previous module-level ``embedding_model`` symbol —
# any direct importer keeps working (raw BedrockEmbeddings instance).
model: EmbeddingModel = TitanEmbedTextV2BedrockModel.model
embedding_model: BedrockEmbeddings = model.model  # type: ignore[assignment]
