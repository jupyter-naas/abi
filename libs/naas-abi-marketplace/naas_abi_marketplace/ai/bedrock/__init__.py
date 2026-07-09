import logging
import os
from typing import Optional

from naas_abi_core.models.Model import ModelProvider
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from pydantic import model_validator

logger = logging.getLogger(__name__)


class BedrockValidationError(RuntimeError):
    """Raised when the Bedrock module cannot authenticate or reach AWS Bedrock."""


class ABIModule(BaseModule):
    name: str = "AWS Bedrock"
    description: str = "AWS Bedrock module for Claude, Llama, Nova, and other foundation models through a unified, IAM-authenticated API."
    logo_url: str = "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/dark/bedrock-color.png"
    tags: list[str] = ["aws", "bedrock", "foundation models"]
    slug: str = "bedrock"
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService, ModelRegistryService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.bedrock
        enabled: true
        config:
            aws_access_key_id: "{{ secret.AWS_ACCESS_KEY_ID }}"
            aws_secret_access_key: "{{ secret.AWS_SECRET_ACCESS_KEY }}"
            aws_session_token: "{{ secret.AWS_SESSION_TOKEN }}"
            region_name: "us-east-1"
            validate_on_load: true
            validation_model_id: null  # optional: invoke this model to prove access
            include_models:            # optional: register only these canonical ids
              - "gpt-oss-120b"
        """

        aws_access_key_id: Optional[str] = None
        aws_secret_access_key: Optional[str] = None
        aws_session_token: Optional[str] = None
        region_name: str = "us-east-1"
        datastore_path: str = "bedrock"

        # When set, only models whose CANONICAL_ID is in this list are
        # registered on load; every other models/*.py file is skipped *without
        # importing it*, which avoids constructing the (slow) Bedrock client for
        # models you don't use. Values are canonical model ids, e.g.
        # ["gpt-oss-120b"]. When None (default), all discovered models load.
        include_models: Optional[list[str]] = None

        # When true (default), the module verifies on load that:
        #   1. boto3 can resolve AWS credentials,
        #   2. sts:GetCallerIdentity succeeds,
        #   3. bedrock:ListFoundationModels succeeds in `region_name`.
        # If `validation_model_id` is also set, a 1-token Converse call is made
        # against that model to prove model-level access.
        # On failure, BedrockValidationError is raised — the module will not load.
        validate_on_load: bool = True
        validation_model_id: Optional[str] = None

        @model_validator(mode="after")
        def _validate_bedrock_access(self) -> "ABIModule.Configuration":
            if not self.validate_on_load:
                return self

            # Auto-skip under pytest so test collection doesn't require AWS access.
            # Users who want to validate during tests can unset PYTEST_CURRENT_TEST
            # or explicitly set validate_on_load=true in a dedicated integration test.
            if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get(
                "BEDROCK_SKIP_VALIDATION"
            ):
                logger.debug(
                    "Bedrock module validation skipped (pytest or "
                    "BEDROCK_SKIP_VALIDATION env var detected)."
                )
                return self

            try:
                import boto3
                from botocore.exceptions import (
                    BotoCoreError,
                    ClientError,
                    NoCredentialsError,
                )
            except ImportError as exc:
                raise BedrockValidationError(
                    "boto3 is required for the Bedrock module. Install with "
                    "`uv pip install \"naas-abi-marketplace[ai-bedrock]\"`."
                ) from exc

            # Only pass credentials explicitly if provided; otherwise let boto3
            # walk its credential chain (env -> shared file -> container -> IMDS).
            session_kwargs: dict = {"region_name": self.region_name}
            if self.aws_access_key_id:
                session_kwargs["aws_access_key_id"] = self.aws_access_key_id
            if self.aws_secret_access_key:
                session_kwargs["aws_secret_access_key"] = self.aws_secret_access_key
            if self.aws_session_token:
                session_kwargs["aws_session_token"] = self.aws_session_token

            try:
                session = boto3.Session(**session_kwargs)
            except (BotoCoreError, ValueError) as exc:
                raise BedrockValidationError(
                    f"Failed to build boto3 Session: {exc}"
                ) from exc

            # Step 1: credentials must resolve.
            creds = session.get_credentials()
            if creds is None:
                raise BedrockValidationError(
                    "No AWS credentials could be resolved. Checked: explicit "
                    "config, env vars, shared credentials file, container "
                    "credentials endpoint, and EC2 IMDS. Attach an IAM role to "
                    "the instance/task/pod or provide credentials in config."
                )
            method = getattr(creds, "method", "unknown")
            logger.info("Bedrock module: resolved AWS credentials via %s", method)

            # Step 2: prove the credentials work.
            try:
                identity = session.client("sts").get_caller_identity()
                logger.info(
                    "Bedrock module: authenticated as %s (account %s)",
                    identity.get("Arn"),
                    identity.get("Account"),
                )
            except (ClientError, BotoCoreError, NoCredentialsError) as exc:
                raise BedrockValidationError(
                    f"sts:GetCallerIdentity failed — credentials resolved via "
                    f"{method} but are not usable: {exc}"
                ) from exc

            # Step 3: prove Bedrock is reachable in the configured region.
            try:
                bedrock = session.client("bedrock", region_name=self.region_name)
                bedrock.list_foundation_models()
                logger.info(
                    "Bedrock module: bedrock:ListFoundationModels succeeded in %s",
                    self.region_name,
                )
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("AccessDeniedException", "UnauthorizedOperation"):
                    raise BedrockValidationError(
                        f"Bedrock is reachable in {self.region_name} but the "
                        f"caller lacks bedrock:ListFoundationModels permission: "
                        f"{exc}"
                    ) from exc
                raise BedrockValidationError(
                    f"bedrock:ListFoundationModels failed in "
                    f"{self.region_name}: {exc}"
                ) from exc
            except BotoCoreError as exc:
                raise BedrockValidationError(
                    f"Could not reach Bedrock endpoint in {self.region_name} "
                    f"(network/VPC endpoint issue?): {exc}"
                ) from exc

            # Step 4 (optional): prove a specific model is invokable.
            if self.validation_model_id:
                try:
                    runtime = session.client(
                        "bedrock-runtime", region_name=self.region_name
                    )
                    runtime.converse(
                        modelId=self.validation_model_id,
                        messages=[
                            {"role": "user", "content": [{"text": "ping"}]}
                        ],
                        inferenceConfig={"maxTokens": 1},
                    )
                    logger.info(
                        "Bedrock module: validated invocation of %s",
                        self.validation_model_id,
                    )
                except (ClientError, BotoCoreError) as exc:
                    raise BedrockValidationError(
                        f"Failed to invoke validation model "
                        f"'{self.validation_model_id}' in {self.region_name}. "
                        f"Has model access been granted in the Bedrock console? "
                        f"Error: {exc}"
                    ) from exc

            return self

    def on_load(self):
        # BaseModule.on_load auto-discovers every models/*.py file that
        # exposes CANONICAL_ID + model and registers them.
        super().on_load()

        # Register the bedrock chat factory for off-catalog model ids.
        from langchain_aws import ChatBedrockConverse

        cfg = self.configuration

        def bedrock_chat_factory(provider_model_id: str) -> ChatBedrockConverse:
            return ChatBedrockConverse(
                model=provider_model_id,
                region_name=cfg.region_name,
                aws_access_key_id=cfg.aws_access_key_id,
                aws_secret_access_key=cfg.aws_secret_access_key,
                aws_session_token=cfg.aws_session_token,
                temperature=0,
                max_tokens=None,
            )

        self.engine.services.model_registry.register_chat_provider(
            ModelProvider.BEDROCK, bedrock_chat_factory
        )
